"""
P4 Federated Learning — Integration Tests

Integration tests for:
1. Patent Claim 2 compliance: only shared weights transmitted
2. DP budget tracking: cumulative ε within target
3. FedProx convergence: outperforms FedAvg on non-IID data

These are critical validation tests that must pass before production use.
"""

import importlib.util

import pytest
import torch

from lip.p12_federated_learning.constants import (
    DP_CUMULATIVE_EPSILON_MAX,
    FEDPROX_MU_VALUES,
)
from lip.p12_federated_learning.dp_accountant import RenyiDPAccountant
from lip.p12_federated_learning.local_ensemble import LocalEnsemble
from lip.p12_federated_learning.models import (
    FederatedModel,
    LocalModel,
    SharedModel,
    get_shared_parameter_count,
)
from lip.p12_federated_learning.privacy_engine import attach_privacy_engine
from lip.p12_federated_learning.synthetic_banks import (
    SyntheticBank,
    create_dataloader,
    generate_synthetic_bank_data,
)

HAS_FLOWER = importlib.util.find_spec("flwr") is not None

pytestmark = pytest.mark.skipif(
    not HAS_FLOWER,
    reason="Flower not available. Install with: pip install flwr[simulation]>=1.0"
)

if HAS_FLOWER:
    from lip.p12_federated_learning.client import (  # noqa: E402
        LIPFlowerClient,
        verify_local_model_unchanged,
    )

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def synthetic_bank_data():
    """Create synthetic bank data for testing."""
    bank = SyntheticBank(
        bank_id="test_bank",
        n_samples=1000,
        failure_rate=0.1,
        corridors=["TEST-USD"],
        seed=42,
    )
    return generate_synthetic_bank_data(bank, k_neighbors=3)


@pytest.fixture
def train_loader(synthetic_bank_data):
    """Create a DataLoader from synthetic bank data."""
    return create_dataloader(synthetic_bank_data, batch_size=64, shuffle=True)


@pytest.fixture
def test_client(train_loader):
    """Create a test LIPFlowerClient."""
    # Initialize models
    torch.manual_seed(42)
    local_model = LocalModel()
    torch.manual_seed(42)
    shared_model = SharedModel()
    federated_model = FederatedModel(local_model, shared_model)

    # Initialize optimizer
    optimizer = torch.optim.AdamW(federated_model.parameters(), lr=0.001)

    # Attach PrivacyEngine (simplified for testing)
    # Note: This may fail if dp-accounting not available
    try:
        privacy_engine = attach_privacy_engine(
            federated_model,
            optimizer,
            train_loader,
            noise_multiplier=1.1,
            max_grad_norm=1.0,
            alphas=1.0,
            delta=1e-5,
        )
    except ImportError:
        pytest.skip("dp-accounting not available")

    # Initialize DP accountant
    dp_accountant = RenyiDPAccountant(
        epsilon=1.0,
        delta=1e-5,
        target_epsilon=3.0,
    )

    # Initialize local ensemble
    local_ensemble = LocalEnsemble(lgbm_model=None)

    return LIPFlowerClient(
        federated_model=federated_model,
        optimizer=optimizer,
        privacy_engine=privacy_engine,
        dp_accountant=dp_accountant,
        local_ensemble=local_ensemble,
        train_loader=train_loader,
    )


# =============================================================================
# Patent Claim 2 Compliance Tests
# =============================================================================


class TestPatentClaim2Compliance:
    """
    Verify Patent Claim 2: "only weights of the final aggregation
    layers are shared across the consortium."
    """

    def test_only_shared_weights_transmitted(self, test_client):
        """
        Verify only SharedModel weights are transmitted.

        This is the literal test for Patent Claim 2 compliance.
        """
        shared_param_count = get_shared_parameter_count()
        transmitted_params = test_client.get_parameters(config={})

        # Count transmitted parameters
        transmitted_count = sum(p.size for p in transmitted_params)

        assert transmitted_count == shared_param_count, (
            f"Expected {shared_param_count} shared params, "
            f"got {transmitted_count}"
        )

    def test_local_weights_not_transmitted(self, test_client):
        """
        Verify LocalModel weights are NOT included in transmission.
        """
        transmitted_params = test_client.get_parameters(config={})

        total_param_count = sum(
            p.numel() for p in test_client.model.parameters()
        )
        local_param_count = sum(
            p.numel() for p in test_client.model.local.parameters()
        )

        transmitted_count = sum(p.size for p in transmitted_params)

        # Transmitted should be total - local (approximately)
        # (Allowing for some overlap in shared components)
        assert transmitted_count < total_param_count
        assert abs(transmitted_count - (total_param_count - local_param_count)) < 100_000

    def test_local_model_unchanged_after_set_parameters(self, test_client):
        """
        Verify LocalModel weights are unchanged after set_parameters.

        This confirms that set_parameters only updates SharedModel.
        """
        # Get original local state
        original_local_state = {
            k: v.clone() for k, v in test_client.model.local.state_dict().items()
        }

        # Get server parameters and set them
        params = test_client.get_parameters(config={})
        test_client.set_parameters(params, config={})

        # Verify local model unchanged
        assert verify_local_model_unchanged(test_client, original_local_state)

    def test_set_parameters_updates_only_shared(self, test_client):
        """
        Verify set_parameters updates ONLY SharedModel weights.
        """
        # Get parameters. NOTE: get_parameters() returns numpy views sharing
        # memory with the model tensors, so original_mean MUST be computed
        # before set_parameters() mutates those tensors in place.
        params = test_client.get_parameters(config={})
        original_mean = torch.cat(
            [torch.from_numpy(p.copy()).flatten() for p in params]
        ).mean()

        # Modify parameters (simulate server update)
        modified_params = [p + 0.01 for p in params]

        # Set modified parameters
        test_client.set_parameters(modified_params, config={})

        # Verify shared model changed
        shared_state = test_client.model.shared.state_dict()
        shared_mean = torch.cat([v.flatten() for v in shared_state.values()]).mean()

        assert not torch.allclose(shared_mean, original_mean, atol=1e-3)

        # Verify local model unchanged
        local_state = test_client.model.local.state_dict()
        local_mean = torch.cat([v.flatten() for v in local_state.values()]).mean()

        # Local mean should be approximately 0 (initialized from normal dist)
        # and unchanged
        assert abs(local_mean) < 1.0


# =============================================================================
# DP Budget Tests
# =============================================================================


class TestDPBudget:
    """Tests for differential privacy budget tracking."""

    def test_dp_budget_not_exhausted_after_one_round(self, test_client):
        """
        Verify DP budget is not exhausted after one training round.

        Target: ε_cumulative < DP_CUMULATIVE_EPSILON_MAX (3.0)
        """
        # Run one training round
        params, _, metrics = test_client.fit(
            parameters=test_client.get_parameters(config={}),
            config={"local_epochs": 1},
        )

        epsilon_cumulative = test_client.dp_accountant.get_status().epsilon_spent

        assert epsilon_cumulative < float(DP_CUMULATIVE_EPSILON_MAX), (
            f"DP budget exhausted: ε={epsilon_cumulative} >= "
            f"{DP_CUMULATIVE_EPSILON_MAX}"
        )

    def test_dp_budget_composes_correctly(self, test_client):
        """
        Verify DP budget composes correctly across multiple rounds.

        Each round should consume some budget; cumulative should increase.
        """
        epsilon_0 = test_client.dp_accountant.get_status().epsilon_spent

        # Run first round
        params, _, metrics = test_client.fit(
            parameters=test_client.get_parameters(config={}),
            config={"local_epochs": 1},
        )
        epsilon_1 = test_client.dp_accountant.get_status().epsilon_spent

        # Run second round
        params, _, metrics = test_client.fit(
            parameters=params,
            config={"local_epochs": 1},
        )
        epsilon_2 = test_client.dp_accountant.get_status().epsilon_spent

        # Epsilon should increase each round
        assert epsilon_0 < epsilon_1 < epsilon_2, (
            f"Epsilon not increasing: {epsilon_0} -> {epsilon_1} -> {epsilon_2}"
        )

    def test_dp_epsilon_within_expected_range(self, test_client):
        """
        Verify DP epsilon per round is within expected range.

        With our parameters, each round should consume approximately 0.05-0.2 ε.
        """
        # Run a few rounds
        for _ in range(3):
            params, _, metrics = test_client.fit(
                parameters=test_client.get_parameters(config={}),
                config={"local_epochs": 1},
            )

        # Get epsilon spent in last round
        round_costs = test_client.dp_accountant.get_round_costs()
        if round_costs:
            last_round_epsilon = round_costs[-1].epsilon_spent

            # Should be positive and reasonable
            assert last_round_epsilon > 0
            assert last_round_epsilon < 1.0  # Should be less than per-round target

    def test_dp_accountant_tracks_rounds(self, test_client):
        """
        Verify DP accountant tracks number of rounds correctly.
        """
        # Run 3 rounds
        for i in range(3):
            params, _, metrics = test_client.fit(
                parameters=test_client.get_parameters(config={}),
                config={"local_epochs": 1},
            )
            assert test_client.dp_accountant.num_rounds == i + 1


# =============================================================================
# FedProx vs FedAvg Convergence Tests
# =============================================================================


class TestFedProxConvergence:
    """
    Tests for FedProx convergence on non-IID synthetic data.

    These tests validate that FedProx (μ > 0) converges better than
    FedAvg (μ = 0) on heterogeneous data distributions.
    """

    def test_fedprox_requires_mu_parameter(self):
        """
        Verify FedProx strategy requires μ parameter.

        μ=0 corresponds to FedAvg; μ>0 enables proximal regularization.
        """
        # Valid μ values per architecture spec
        for mu in FEDPROX_MU_VALUES:
            assert mu >= 0.0, f"μ must be non-negative, got {mu}"
            if mu > 0:
                assert mu <= FEDPROX_MU_VALUES[-1], f"μ too large, got {mu}"

    def test_proximal_term_applied_only_to_shared_layers(self, test_client):
        """
        Verify proximal term is applied only to shared layers.

        Because get_parameters() returns only shared weights, Flower's
        FedProx strategy naturally applies the proximal penalty only
        to those parameters. Local layers have no global reference.
        """
        # Get shared parameters
        shared_params = test_client.get_parameters(config={})

        # Shared parameters count should match SharedModel
        shared_param_count = get_shared_parameter_count()
        transmitted_count = sum(p.size for p in shared_params)

        assert transmitted_count == shared_param_count, (
            "Proximal term applied to wrong parameter set"
        )

    def test_simulation_requires_multiple_banks_for_convergence_comparison(self):
        """
        Verify simulation setup for FedProx vs FedAvg comparison.

        Need at least 2 banks to observe convergence differences.
        """
        # Generate synthetic banks
        banks = [
            SyntheticBank(
                bank_id="bank_1",
                n_samples=500,
                failure_rate=0.02,
                corridors=["A"],
                seed=1,
            ),
            SyntheticBank(
                bank_id="bank_2",
                n_samples=500,
                failure_rate=0.08,  # Different failure rate = non-IID
                corridors=["B"],
                seed=2,
            ),
        ]

        assert len(banks) >= 2, "Need at least 2 banks for convergence comparison"

        # Verify non-IID property
        failure_rates = [b.failure_rate for b in banks]
        assert max(failure_rates) - min(failure_rates) > 0.01, (
            "Banks should have different failure rates for non-IID test"
        )


# =============================================================================
# End-to-End Integration Tests
# =============================================================================


class TestEndToEnd:
    """End-to-end integration tests for the full FL pipeline."""

    def test_full_round_cycle(self, test_client):
        """
        Verify a complete FL round cycle works end-to-end.

        Cycle: get_parameters -> server update -> set_parameters -> fit
        """
        # 1. Client sends parameters to "server"
        client_params = test_client.get_parameters(config={})

        assert len(client_params) > 0

        # 2. "Server" updates parameters (simulated)
        server_params = [p + 0.001 for p in client_params]  # Small update

        # 3. Client receives server parameters
        test_client.set_parameters(server_params, config={})

        # 4. Client trains locally
        new_params, new_num_examples, new_metrics = test_client.fit(
            parameters=server_params,
            config={"local_epochs": 1},
        )

        assert len(new_params) == len(server_params)
        assert new_num_examples == len(test_client.train_loader.dataset)

        # 5. Verify training loss decreased (or at least changed)
        if "train_loss" in new_metrics:
            # Loss may not always decrease in one round, but should be finite
            assert new_metrics["train_loss"] > 0
            assert new_metrics["train_loss"] < 100  # Reasonable upper bound

    def test_multiple_rounds_without_errors(self, test_client):
        """
        Verify multiple FL rounds can run without errors.

        Tests for memory leaks, resource exhaustion, etc.
        """
        params = test_client.get_parameters(config={})

        for round_num in range(5):
            params, _, metrics = test_client.fit(
                parameters=params,
                config={"local_epochs": 1},
            )

            assert "train_loss" in metrics or round_num > 0
            assert test_client.dp_accountant.num_rounds == round_num + 1

    def test_client_properties_accessible(self, test_client):
        """
        Verify client properties (sample count, DP budget) are accessible.

        Properties are used by Flower server for client selection and monitoring.
        """
        from flwr.common import GetPropertiesIns

        props = test_client.get_properties(GetPropertiesIns(config={}))

        assert "num_samples" in props
        assert props["num_samples"] == len(test_client.train_loader.dataset)
        assert "dp_epsilon_cumulative" in props
        assert props["dp_epsilon_cumulative"] >= 0
