# Proposed PIT relation contract — not implemented or passed

This contract records the minimum needed for any separate historical reconstruction. It does not make the current JP_Market_Vis snapshot PIT and does not authorize Phase 2 by itself.

## Edge definition and direction

- Include only listed-to-listed `major_customer` evidence from the supplier's own disclosure. Edge direction is `supplier_code -> customer_code`.
- Exclude ownership, alliances, personnel, group membership, transaction partners, adoptions, ambiguous direction, and any inferred link.
- Treat fiscal period-end/economic effective date as an attribute, never as the feature availability date.

## Availability timestamp

- Preserve filing/document ID, original URL, EDINET issuer identifier, period end, actual filing/publication timestamp, retrieval timestamp, source hash, parser version, relation status, and both endpoint names/codes.
- Availability is the first conservative timestamp when a market participant could access the filing. Prefer an official timestamp. If only a date is available, assign 23:59:59 JST and permit use only from the next Japanese trading session. This follows the competition's conservative date-only public-feature convention.
- At signal date `t`, only use edges whose conservative availability timestamp is no later than the close of `t`.

## Status updates and termination

- Build a dated supplier customer-set snapshot from every relevant subsequent annual report/amendment. A successor filing with a complete, unambiguous major-customer section replaces the prior set as of its safe availability date; an edge not present in that updated set ends then.
- If the successor document is missing, incomplete, or extraction is ambiguous, mark that supplier's relation state unknown and exclude its edges until a later complete disclosure. Do not silently carry the prior list forever.
- A one-annual-cycle forward carry from a dated observation is permitted as the fixed persistence assumption. If no complete successor filing is available within 12 months of the last safe availability date, the supplier's relation state becomes unknown until reconfirmed. Each complete annual filing that re-lists the edge refreshes the availability/age clock, allowing multi-year persistence through repeated PIT confirmation. Do not use a multi-year, unrefreshed carry as the default.
- Retain start, supersession/termination, and unknown intervals with the filing IDs that caused each transition. Do not infer a termination date from a later economic period end.
- A parser must distinguish “complete section with no qualifying customer” from “section not parsed / filing not available.” No inferred zero-customer value.

This one-cycle assumption is supported as a prior by Japanese network studies: one study of annual links for over 500,000 firms in 2008-2012 estimates 92% annual customer-link and 93% supplier-link survival; a separate 2007-2016 panel finds survival increasing with relationship tenure. These are broader inter-firm links, not a direct persistence estimate for JMV's ≥10%-of-sales major-customer disclosure category. The assumption permits forward carry after a historical public observation; it cannot establish the missing first public observation in Train.

## Endpoint mapping and price coverage

- Resolve supplier identity from the contemporaneous filing identifier and point-in-time listed-company record. Do not join today's JMV M4 codes/aliases into earlier years.
- Resolve each customer name to contemporaneous point-in-time listed metadata and the competition price universe. Accept only unique exact/controlled-alias matches; record ambiguous, unmatched, delisted, and outside-basket counts separately and exclude them.
- A customer contributes only where all required prior 20 customer residual returns and the existing PIT beta/TOPIX inputs are finite and inside that customer's listing segment. No backward filling or code reuse across listings.

## Gate evidence still required

An implementation must show annual filing coverage by issuer, `available_date <= t` edge counts, listed-listed mapped edge counts, supplier coverage, customer price coverage, customer-count distribution, relation age/update/termination statistics, mapping ambiguities, and future-dated exclusions. It must then run future-edge mutation, future-return mutation, prefix-invariance, firewall, and deterministic construction/prediction checks. The persistence assumption does not alter the current finding: without historical first-public observations, Phase 1 remains `PIT INSUFFICIENT`.
