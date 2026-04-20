# FluxGuardian Demo Queries

Five example questions that showcase the bot's capabilities with the FoodieExpress dataset.

---

## 1. Blast Radius — "what breaks if I drop users.email?"

**Trigger:** `/fluxguardian what breaks if I drop users.email?`

**What Claude does:**
- Calls `get_column_impact("foodieexpress.public.users.email")`
- Sees 4 affected assets (CFO dashboard, Churn Predictor, ETL pipeline, marketing cohorts)
- Notes PII.Email tag → governance flag

**Expected answer (roughly):**
```
🔴 *Dropping `users.email` has critical impact across 4 assets:*

• 🟠 *CFO Weekly Revenue* (dashboard) — owner: @priya
• 🟠 *Churn Predictor v2* (ML model) — owner: @arjun
• 🟡 *daily_revenue_etl* (pipeline) — owner: @priya
• 🟡 *marketing_regional_cohorts* (dashboard) — owner: @raj

> ⚠️ `users.email` is tagged *PII.Email* — governance approval required before dropping.

Ping @priya, @arjun, and @raj before merging this migration.
```

---

## 2. Ownership — "who owns the CFO dashboard?"

**Trigger:** `/fluxguardian who owns the CFO dashboard?`

**What Claude does:**
- Calls `search_assets("CFO dashboard")` to find the FQN
- Calls `find_owner("Looker.cfo_weekly_revenue")`

**Expected answer:**
```
*CFO Weekly Revenue* (Looker dashboard) is owned by *Priya* (@priya).

FQN: `Looker.cfo_weekly_revenue`
```

---

## 3. PII Audit — "show me all PII columns in our database"

**Trigger:** `/fluxguardian show me all PII columns in our database`

**What Claude does:**
- Calls `list_pii_columns()`
- Groups results by PII type

**Expected answer:**
```
*PII-classified columns in FoodieExpress:*

*📧 PII.Email*
• `users.email`

*📞 PII.Phone*
• `users.phone`
• `restaurants.owner_contact`
• `deliveries.driver_phone`

*💳 PII.Financial*
• `orders.amount_cents`
• `payments.card_last_4`

6 columns total. Make sure downstream consumers have appropriate access controls.
```

---

## 4. Owner's Assets — "which assets does priya own?"

**Trigger:** `/fluxguardian which assets does priya own?`

**What Claude does:**
- Calls `search_assets("priya")` to find assets linked to priya
- May call `find_owner` on individual assets to confirm

**Expected answer:**
```
*Assets owned by Priya* (@priya):

• `Looker.cfo_weekly_revenue` — dashboard
• `Airflow.daily_revenue_etl` — pipeline

> Priya is the primary contact for revenue-facing data. Tag @priya in PRs that touch the `orders` or `users` tables.
```

---

## 5. PII Check — "is users.phone tagged as PII?"

**Trigger:** `/fluxguardian is users.phone tagged as PII?`

**What Claude does:**
- Calls `get_column_impact("users.phone")` to see tags
- Notes PII.Phone tag and lists downstream consumers

**Expected answer:**
```
Yes — `users.phone` is tagged *PII.Phone*.

*Downstream consumers:*
• 🟠 *Support Agent Console* (Metabase) — owner: @kavya
• 🟡 *customer_enrichment_etl* (dbt pipeline) — unowned

> Any schema change to `users.phone` requires a PII impact review. Ping @kavya before proceeding.
```

---

## Bonus — Complex Multi-Tool Question

**Trigger:** `/fluxguardian what's the riskiest table to change and why?`

Claude will:
1. Call `list_pii_columns()` to find PII-heavy tables
2. Call `get_column_impact("users.email")` and `get_column_impact("users.phone")` 
3. Call `search_assets("users")` to get full asset context
4. Synthesize a ranked risk assessment

This demonstrates multi-step reasoning across all four tools.
