# Spec 05: Mathematical Optimization & Marketing Trap Auditor

> **Status**: Approved & Verified  
> **Source Directory**: `sabad/optimizer/`  
> **Engines**: `milp_solver.py`, `single_store.py`, `trap_auditor.py`

---

## 1. Problem Formulation

The grocery basket allocation problem is modeled as a **Mixed-Integer Linear Program (MILP)** minimizing the total customer outlay across item purchase costs, tiered delivery fees, and multi-store delivery friction.

### Sets & Indices
- $I = \{1, \dots, N\}$: Set of items in the parsed grocery basket.
- $S = \{\text{snapp\_market}, \text{digikala\_jet}, \text{okala}\}$: Set of supermarket platforms.

### Parameters
- $q_i \in \mathbb{N}_{\ge 1}$: Quantity demanded for item $i$.
- $p_{i,s} \in \mathbb{R}^+$: Selling unit price (in Tomans) of item $i$ at store $s$.
- $a_{i,s} \in \{0, 1\}$: Availability indicator (1 if in stock and strictly matches item $i$ attributes, 0 otherwise).
- $\text{MOV}_s \in \mathbb{R}^+$: Minimum Order Value for store $s$ (in Tomans).
- $\text{Fee}_s(\text{Subtotal}_s)$: Non-linear tiered shipping function for store $s$.
- $P_{\text{split}} \in \mathbb{R}^+$: Multi-store coordination friction penalty (default: 25,000 Tomans).

### Decision Variables
- $x_{i,s} \in \{0, 1\}$: Binary assignment of item $i$ to store $s$.
- $y_s \in \{0, 1\}$: Binary store activation (1 if any item is purchased from store $s$).

---

## 2. Objective Function

$$\min_{x, y} \sum_{s \in S} \left( \sum_{i \in I} p_{i,s} \cdot q_i \cdot x_{i,s} + \text{Fee}_s\left(\sum_{i \in I} p_{i,s} \cdot q_i \cdot x_{i,s}\right) \right) + P_{\text{split}} \cdot \max(0, \sum_{s \in S} y_s - 1)$$

### Constraints
1. **Full Basket Demand Coverage**:
   $$\sum_{s \in S} x_{i,s} = 1 \quad \forall i \in I$$
2. **Item Stock & Compatibility**:
   $$x_{i,s} \le a_{i,s} \quad \forall i \in I, \forall s \in S$$
3. **Store Activation Coupling**:
   $$x_{i,s} \le y_s \quad \forall i \in I, \forall s \in S$$
4. **Minimum Order Value (MOV) Guard**:
   $$\sum_{i \in I} p_{i,s} \cdot q_i \cdot x_{i,s} \ge \text{MOV}_s \cdot y_s \quad \forall s \in S$$

---

## 3. Tiered Shipping Evaluation (`single_store.py`)

Delivery fees are calculated dynamically based on store-specific delivery tiers:
```python
def calculate_delivery_fee(subtotal: float, store_info: StoreInfo) -> float:
    for tier in store_info.delivery_tiers:
        if tier.max_subtotal is None:
            if subtotal >= tier.min_subtotal:
                return tier.fee
        elif tier.min_subtotal <= subtotal < tier.max_subtotal:
            return tier.fee
    return 30000.0  # Fallback default shipping fee in Tomans
```

---

## 4. Flash Deal Marketing Trap Auditor (`trap_auditor.py`)

Online supermarkets frequently offer deep discounts on popular "bait" items (*loss leaders*) while surreptitiously marking up other daily essentials or forcing users into extra delivery fee brackets.

The **Trap Auditor** evaluates every discounted item $k$ with apparent saving $\Delta_{\text{deal}}$:

$$\Delta_{\text{deal}} = (p_{\text{base}, k} - p_{\text{selling}, k}) \cdot q_k$$

$$\Delta_{\text{collateral\_markup}} = \sum_{j \neq k} \max\left(0, p_{j, \text{deal\_store}} - \min_{s \neq \text{deal\_store}} p_{j,s}\right) \cdot q_j$$

$$\Delta_{\text{extra\_shipping}} = \text{Fee}_{\text{deal\_store}} - \min_{s} \text{Fee}_s$$

### Net Advantage Formulation
$$\text{NetAdvantage} = \Delta_{\text{deal}} - (\Delta_{\text{collateral\_markup}} + \Delta_{\text{extra\_shipping}})$$

### Audit Classification:
- **`is_trap = True` (تله بازاریابی)**: If $\text{NetAdvantage} < 0$. The user loses money by buying the discounted item at this store because collateral items are overpriced.
- **`is_trap = False` (تخفیف واقعی)**: If $\text{NetAdvantage} \ge 0$. The discount provides genuine economic savings.
