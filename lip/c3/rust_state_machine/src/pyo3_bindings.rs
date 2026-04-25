use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

use crate::iso20022;
use crate::state_machine::PaymentState;
use crate::taxonomy;

// ---------------------------------------------------------------------------
// Helper: convert a PyDict to serde_json::Value (shallow + recursive)
// ---------------------------------------------------------------------------

fn pydict_to_json(py: Python<'_>, dict: &Bound<'_, PyDict>) -> PyResult<serde_json::Value> {
    let mut map = serde_json::Map::new();
    for (k, v) in dict.iter() {
        let key = k.extract::<String>()?;
        let value = pyobj_to_json(py, &v)?;
        map.insert(key, value);
    }
    Ok(serde_json::Value::Object(map))
}

fn pyobj_to_json(py: Python<'_>, obj: &Bound<'_, PyAny>) -> PyResult<serde_json::Value> {
    if obj.is_none() {
        return Ok(serde_json::Value::Null);
    }
    if let Ok(b) = obj.extract::<bool>() {
        return Ok(serde_json::Value::Bool(b));
    }
    if let Ok(i) = obj.extract::<i64>() {
        return Ok(serde_json::Value::Number(i.into()));
    }
    if let Ok(f) = obj.extract::<f64>() {
        if let Some(n) = serde_json::Number::from_f64(f) {
            return Ok(serde_json::Value::Number(n));
        }
    }
    if let Ok(s) = obj.extract::<String>() {
        return Ok(serde_json::Value::String(s));
    }
    if let Ok(d) = obj.downcast::<PyDict>() {
        return pydict_to_json(py, d);
    }
    if let Ok(lst) = obj.downcast::<PyList>() {
        let mut arr = Vec::new();
        for item in lst.iter() {
            arr.push(pyobj_to_json(py, &item)?);
        }
        return Ok(serde_json::Value::Array(arr));
    }
    // Unknown type — fail closed with TypeError rather than silently coercing to string.
    // Callers must pass dicts with JSON-serialisable values only.
    Err(PyTypeError::new_err(format!(
        "Cannot convert Python type '{}' to JSON: only str, int, float, bool, None, dict, list are supported",
        obj.get_type().name()?
    )))
}

// ---------------------------------------------------------------------------
// PyPaymentStateMachine — wraps a PaymentState with mutation via transition()
// ---------------------------------------------------------------------------

/// Python-exposed payment state machine.
///
/// Enforces the LIP payment lifecycle state machine (Architecture Spec S6).
/// Illegal transitions raise ValueError — never silently downgrade.
#[pyclass(name = "PaymentStateMachine")]
pub struct PyPaymentStateMachine {
    state: PaymentState,
}

#[pymethods]
impl PyPaymentStateMachine {
    /// Create a new state machine starting at `initial_state` (default: "MONITORING").
    ///
    /// Raises:
    ///     ValueError: If `initial_state` is not a valid PaymentState string.
    #[new]
    #[pyo3(signature = (initial_state = "MONITORING"))]
    fn new(initial_state: &str) -> PyResult<Self> {
        let state = PaymentState::from_str(initial_state).map_err(|e| {
            PyValueError::new_err(format!("Invalid PaymentState: {e}"))
        })?;
        Ok(PyPaymentStateMachine { state })
    }

    /// The current payment state as a string.
    #[getter]
    fn current_state(&self) -> &'static str {
        self.state.as_str()
    }

    /// True when the machine has reached a terminal state.
    #[getter]
    fn is_terminal(&self) -> bool {
        self.state.is_terminal()
    }

    /// Advance the machine to `new_state`.
    ///
    /// Raises:
    ///     ValueError: If the transition is not permitted.
    fn transition(&mut self, new_state: &str) -> PyResult<()> {
        let target = PaymentState::from_str(new_state).map_err(|e| {
            PyValueError::new_err(format!("Invalid PaymentState: {e}"))
        })?;
        self.state = self.state.transition(target).map_err(|e| {
            PyValueError::new_err(format!("{e}"))
        })?;
        Ok(())
    }

    /// Return the list of states reachable from the current state.
    fn allowed_transitions<'py>(&self, py: Python<'py>) -> Bound<'py, PyList> {
        let names: Vec<&str> = self
            .state
            .allowed_transitions()
            .iter()
            .map(|s| s.as_str())
            .collect();
        PyList::new_bound(py, names)
    }

    fn __repr__(&self) -> String {
        format!(
            "PaymentStateMachine(current_state={:?}, is_terminal={})",
            self.state.as_str(),
            self.state.is_terminal()
        )
    }
}

// ---------------------------------------------------------------------------
// Taxonomy functions
// ---------------------------------------------------------------------------

/// Classify an ISO 20022 rejection code.
///
/// Returns: one of "CLASS_A", "CLASS_B", "CLASS_C", "BLOCK".
///
/// Raises:
///     ValueError: For unknown codes.
#[pyfunction]
fn classify_rejection_code(code: &str) -> PyResult<&'static str> {
    taxonomy::classify(code)
        .map(|cls| cls.as_str())
        .map_err(|e| PyValueError::new_err(format!("{e}")))
}

/// Return the maturity window in days for a rejection class string.
///
/// Args:
///     rejection_class: One of "CLASS_A", "CLASS_B", "CLASS_C", "BLOCK".
///
/// Returns:
///     int: Maturity days (3, 7, 21, or 0).
///
/// Raises:
///     ValueError: For unknown class strings.
#[pyfunction]
fn maturity_days_for_class(rejection_class: &str) -> PyResult<u32> {
    let cls = match rejection_class {
        "CLASS_A" => taxonomy::RejectionClass::ClassA,
        "CLASS_B" => taxonomy::RejectionClass::ClassB,
        "CLASS_C" => taxonomy::RejectionClass::ClassC,
        "BLOCK" => taxonomy::RejectionClass::Block,
        other => {
            return Err(PyValueError::new_err(format!(
                "Unknown rejection class: '{other}'. Must be one of CLASS_A, CLASS_B, CLASS_C, BLOCK."
            )))
        }
    };
    Ok(taxonomy::maturity_days(cls))
}

/// Return True if the rejection code maps to the BLOCK class.
///
/// Returns False for unknown codes — never raises.
#[pyfunction]
fn is_block_code(code: &str) -> bool {
    taxonomy::is_block(code)
}

// ---------------------------------------------------------------------------
// ISO 20022 field extraction
// ---------------------------------------------------------------------------

/// Extract normalised fields from a camt.054 dict.
///
/// Args:
///     raw_message: Python dict representing the camt.054 message.
///         Accepts both nested ISO 20022 key structure and flat dicts.
///
/// Returns:
///     dict with keys: uetr, individual_payment_id, amount, currency,
///           settlement_time (str|None), rejection_code (str|None)
///
/// Raises:
///     ValueError: On parse failure.
#[pyfunction]
fn extract_camt054_fields<'py>(
    py: Python<'py>,
    raw_message: &Bound<'py, PyDict>,
) -> PyResult<Bound<'py, PyDict>> {
    let msg = pydict_to_json(py, raw_message)?;

    // Navigate nested ISO 20022 path: BkToCstmrDbtCdtNtfctn → Ntfctn[0] → Ntry[0]
    let notification = msg
        .get("BkToCstmrDbtCdtNtfctn")
        .and_then(|v| v.get("Ntfctn"))
        .and_then(|v| v.get(0))
        .unwrap_or(&msg);

    let entry = notification.get("Ntry").and_then(|v| v.get(0));

    let txn_details = entry
        .and_then(|e| e.get("NtryDtls"))
        .and_then(|d| d.get("TxDtls"));

    let fields = iso20022::extract_camt054(Some(notification), entry, txn_details, &msg)
        .map_err(|e| PyValueError::new_err(format!("camt.054 field extraction failed: {e}")))?;

    let result = PyDict::new_bound(py);
    result.set_item("uetr", &fields.uetr)?;
    result.set_item("individual_payment_id", &fields.individual_payment_id)?;
    result.set_item("amount", &fields.amount)?;
    result.set_item("currency", &fields.currency)?;
    result.set_item("settlement_time", fields.settlement_time.as_deref())?;
    result.set_item("rejection_code", fields.rejection_code.as_deref())?;
    Ok(result)
}

/// Extract normalised fields from a pacs.008 dict.
///
/// Args:
///     raw_message: Python dict representing the pacs.008 message.
///         Accepts both nested ISO 20022 key structure and flat dicts.
///
/// Returns:
///     dict with keys: uetr, end_to_end_id, amount, currency,
///           settlement_date (str|None), debtor_bic (str|None), creditor_bic (str|None)
///
/// Raises:
///     ValueError: On parse failure.
#[pyfunction]
fn extract_pacs008_fields<'py>(
    py: Python<'py>,
    raw_message: &Bound<'py, PyDict>,
) -> PyResult<Bound<'py, PyDict>> {
    let msg = pydict_to_json(py, raw_message)?;

    let fields = iso20022::extract_pacs008(&msg)
        .map_err(|e| PyValueError::new_err(format!("pacs.008 field extraction failed: {e}")))?;

    let result = PyDict::new_bound(py);
    result.set_item("uetr", &fields.uetr)?;
    result.set_item("end_to_end_id", &fields.end_to_end_id)?;
    result.set_item("amount", &fields.amount)?;
    result.set_item("currency", &fields.currency)?;
    result.set_item("settlement_date", fields.settlement_date.as_deref())?;
    result.set_item("debtor_bic", fields.debtor_bic.as_deref())?;
    result.set_item("creditor_bic", fields.creditor_bic.as_deref())?;
    Ok(result)
}

// ---------------------------------------------------------------------------
// Module registration
// ---------------------------------------------------------------------------

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyPaymentStateMachine>()?;
    m.add_function(wrap_pyfunction!(classify_rejection_code, m)?)?;
    m.add_function(wrap_pyfunction!(maturity_days_for_class, m)?)?;
    m.add_function(wrap_pyfunction!(is_block_code, m)?)?;
    m.add_function(wrap_pyfunction!(extract_camt054_fields, m)?)?;
    m.add_function(wrap_pyfunction!(extract_pacs008_fields, m)?)?;
    Ok(())
}
