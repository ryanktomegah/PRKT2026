/// state_machine.rs — C3 payment lifecycle state machine
///
/// Architecture Spec S6: PaymentState enum with exhaustive transition table.
/// Illegal transitions are unrepresentable — `transition()` returns
/// `Result<PaymentState, TransitionError>`, never panics, never silently downgrades.
use thiserror::Error;

/// All valid states for a cross-border payment in the LIP system.
///
/// Terminal states (REPAID, BUFFER_REPAID, DEFAULTED, OFFER_DECLINED,
/// OFFER_EXPIRED, DISPUTE_BLOCKED, AML_BLOCKED) have no outgoing transitions.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum PaymentState {
    Monitoring,
    FailureDetected,
    BridgeOffered,
    Funded,
    RepaymentPending,
    CancellationAlert,
    // Terminal states
    Repaid,
    BufferRepaid,
    Defaulted,
    OfferDeclined,
    OfferExpired,
    DisputeBlocked,
    AmlBlocked,
}

/// Error returned when a forbidden state-machine transition is attempted.
#[derive(Debug, Error)]
#[error("Invalid transition: {from} → {to} is not permitted")]
pub struct TransitionError {
    pub from: String,
    pub to: String,
}

/// Error returned when an unknown state string is provided.
#[derive(Debug, Error)]
#[error("Unknown payment state: '{0}'")]
pub struct InvalidStateError(pub String);

impl PaymentState {
    /// Attempt to transition to `target`.
    ///
    /// Returns `Ok(target)` if the transition is permitted by the Architecture
    /// Spec S6 transition table. Returns `Err(TransitionError)` on illegal moves,
    /// including any transition out of a terminal state.
    ///
    /// Fail-closed contract: this function never panics; all arms are exhaustive.
    pub fn transition(&self, target: PaymentState) -> Result<PaymentState, TransitionError> {
        if self.allows(&target) {
            Ok(target)
        } else {
            Err(TransitionError {
                from: self.as_str().to_string(),
                to: target.as_str().to_string(),
            })
        }
    }

    /// Return true if `target` is reachable from the current state.
    fn allows(&self, target: &PaymentState) -> bool {
        match self {
            PaymentState::Monitoring => matches!(
                target,
                PaymentState::FailureDetected
                    | PaymentState::DisputeBlocked
                    | PaymentState::AmlBlocked
            ),
            PaymentState::FailureDetected => matches!(
                target,
                PaymentState::BridgeOffered
                    | PaymentState::DisputeBlocked
                    | PaymentState::AmlBlocked
            ),
            PaymentState::BridgeOffered => matches!(
                target,
                PaymentState::Funded | PaymentState::OfferDeclined | PaymentState::OfferExpired
            ),
            PaymentState::Funded => matches!(
                target,
                PaymentState::Repaid
                    | PaymentState::BufferRepaid
                    | PaymentState::Defaulted
                    | PaymentState::RepaymentPending
                    | PaymentState::CancellationAlert
            ),
            PaymentState::RepaymentPending => matches!(
                target,
                PaymentState::Repaid | PaymentState::BufferRepaid | PaymentState::Defaulted
            ),
            PaymentState::CancellationAlert => matches!(
                target,
                PaymentState::Repaid | PaymentState::Defaulted | PaymentState::Funded
            ),
            // Terminal states: no outgoing transitions
            PaymentState::Repaid
            | PaymentState::BufferRepaid
            | PaymentState::Defaulted
            | PaymentState::OfferDeclined
            | PaymentState::OfferExpired
            | PaymentState::DisputeBlocked
            | PaymentState::AmlBlocked => false,
        }
    }

    /// Return true if this state is terminal (no outgoing transitions).
    pub fn is_terminal(&self) -> bool {
        matches!(
            self,
            PaymentState::Repaid
                | PaymentState::BufferRepaid
                | PaymentState::Defaulted
                | PaymentState::OfferDeclined
                | PaymentState::OfferExpired
                | PaymentState::DisputeBlocked
                | PaymentState::AmlBlocked
        )
    }

    /// Return all states reachable from the current state.
    pub fn allowed_transitions(&self) -> Vec<PaymentState> {
        match self {
            PaymentState::Monitoring => vec![
                PaymentState::FailureDetected,
                PaymentState::DisputeBlocked,
                PaymentState::AmlBlocked,
            ],
            PaymentState::FailureDetected => vec![
                PaymentState::BridgeOffered,
                PaymentState::DisputeBlocked,
                PaymentState::AmlBlocked,
            ],
            PaymentState::BridgeOffered => vec![
                PaymentState::Funded,
                PaymentState::OfferDeclined,
                PaymentState::OfferExpired,
            ],
            PaymentState::Funded => vec![
                PaymentState::Repaid,
                PaymentState::BufferRepaid,
                PaymentState::Defaulted,
                PaymentState::RepaymentPending,
                PaymentState::CancellationAlert,
            ],
            PaymentState::RepaymentPending => vec![
                PaymentState::Repaid,
                PaymentState::BufferRepaid,
                PaymentState::Defaulted,
            ],
            PaymentState::CancellationAlert => vec![
                PaymentState::Repaid,
                PaymentState::Defaulted,
                PaymentState::Funded,
            ],
            // Terminal states
            PaymentState::Repaid
            | PaymentState::BufferRepaid
            | PaymentState::Defaulted
            | PaymentState::OfferDeclined
            | PaymentState::OfferExpired
            | PaymentState::DisputeBlocked
            | PaymentState::AmlBlocked => vec![],
        }
    }

    /// Return the canonical string representation (matches Python enum values).
    pub fn as_str(&self) -> &'static str {
        match self {
            PaymentState::Monitoring => "MONITORING",
            PaymentState::FailureDetected => "FAILURE_DETECTED",
            PaymentState::BridgeOffered => "BRIDGE_OFFERED",
            PaymentState::Funded => "FUNDED",
            PaymentState::RepaymentPending => "REPAYMENT_PENDING",
            PaymentState::CancellationAlert => "CANCELLATION_ALERT",
            PaymentState::Repaid => "REPAID",
            PaymentState::BufferRepaid => "BUFFER_REPAID",
            PaymentState::Defaulted => "DEFAULTED",
            PaymentState::OfferDeclined => "OFFER_DECLINED",
            PaymentState::OfferExpired => "OFFER_EXPIRED",
            PaymentState::DisputeBlocked => "DISPUTE_BLOCKED",
            PaymentState::AmlBlocked => "AML_BLOCKED",
        }
    }

    /// Parse a state from its canonical string representation.
    pub fn from_str(s: &str) -> Result<Self, InvalidStateError> {
        match s {
            "MONITORING" => Ok(PaymentState::Monitoring),
            "FAILURE_DETECTED" => Ok(PaymentState::FailureDetected),
            "BRIDGE_OFFERED" => Ok(PaymentState::BridgeOffered),
            "FUNDED" => Ok(PaymentState::Funded),
            "REPAYMENT_PENDING" => Ok(PaymentState::RepaymentPending),
            "CANCELLATION_ALERT" => Ok(PaymentState::CancellationAlert),
            "REPAID" => Ok(PaymentState::Repaid),
            "BUFFER_REPAID" => Ok(PaymentState::BufferRepaid),
            "DEFAULTED" => Ok(PaymentState::Defaulted),
            "OFFER_DECLINED" => Ok(PaymentState::OfferDeclined),
            "OFFER_EXPIRED" => Ok(PaymentState::OfferExpired),
            "DISPUTE_BLOCKED" => Ok(PaymentState::DisputeBlocked),
            "AML_BLOCKED" => Ok(PaymentState::AmlBlocked),
            other => Err(InvalidStateError(other.to_string())),
        }
    }
}

// ---------------------------------------------------------------------------
// Unit tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_happy_path_monitoring_to_funded() {
        let s = PaymentState::Monitoring;
        let s = s.transition(PaymentState::FailureDetected).unwrap();
        let s = s.transition(PaymentState::BridgeOffered).unwrap();
        let s = s.transition(PaymentState::Funded).unwrap();
        let s = s.transition(PaymentState::RepaymentPending).unwrap();
        let s = s.transition(PaymentState::Repaid).unwrap();
        assert!(s.is_terminal());
        assert_eq!(s.as_str(), "REPAID");
    }

    #[test]
    fn test_terminal_repaid_cannot_transition() {
        let s = PaymentState::Repaid;
        let err = s.transition(PaymentState::Monitoring).unwrap_err();
        assert!(err.to_string().contains("REPAID"));
        assert!(err.to_string().contains("MONITORING"));
    }

    #[test]
    fn test_terminal_defaulted_cannot_transition() {
        let s = PaymentState::Defaulted;
        let err = s.transition(PaymentState::Funded).unwrap_err();
        assert!(err.to_string().contains("DEFAULTED"));
    }

    #[test]
    fn test_dispute_blocked_is_terminal() {
        let s = PaymentState::DisputeBlocked;
        assert!(s.is_terminal());
        assert!(s.allowed_transitions().is_empty());
    }

    #[test]
    fn test_aml_blocked_is_terminal() {
        let s = PaymentState::AmlBlocked;
        assert!(s.is_terminal());
        assert!(s.allowed_transitions().is_empty());
    }

    #[test]
    fn test_cancellation_alert_can_return_to_funded() {
        let s = PaymentState::CancellationAlert;
        let s = s.transition(PaymentState::Funded).unwrap();
        assert_eq!(s.as_str(), "FUNDED");
    }

    #[test]
    fn test_monitoring_cannot_jump_to_repaid() {
        let s = PaymentState::Monitoring;
        assert!(s.transition(PaymentState::Repaid).is_err());
    }

    #[test]
    fn test_roundtrip_string_conversion() {
        let states = [
            "MONITORING",
            "FAILURE_DETECTED",
            "BRIDGE_OFFERED",
            "FUNDED",
            "REPAYMENT_PENDING",
            "CANCELLATION_ALERT",
            "REPAID",
            "BUFFER_REPAID",
            "DEFAULTED",
            "OFFER_DECLINED",
            "OFFER_EXPIRED",
            "DISPUTE_BLOCKED",
            "AML_BLOCKED",
        ];
        for name in states {
            let parsed = PaymentState::from_str(name).unwrap();
            assert_eq!(parsed.as_str(), name);
        }
    }

    #[test]
    fn test_from_str_unknown_state() {
        let err = PaymentState::from_str("INVALID_STATE").unwrap_err();
        assert!(err.to_string().contains("INVALID_STATE"));
    }

    #[test]
    fn test_non_terminal_states_have_transitions() {
        let non_terminal = [
            PaymentState::Monitoring,
            PaymentState::FailureDetected,
            PaymentState::BridgeOffered,
            PaymentState::Funded,
            PaymentState::RepaymentPending,
            PaymentState::CancellationAlert,
        ];
        for state in non_terminal {
            assert!(
                !state.allowed_transitions().is_empty(),
                "{} should have outgoing transitions",
                state.as_str()
            );
        }
    }
}
