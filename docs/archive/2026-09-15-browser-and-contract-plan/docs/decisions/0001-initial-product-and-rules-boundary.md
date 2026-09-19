# 0001: Initial product and rules boundary

This record captures a product-owner decision made before the repository's first integration commit. The owning current documents state the accepted policy at commit `fa8e89d3b73373918d6a2a5727da1cd030673cb7`. Registry formalization awaits the product owner's stable principal ID.

**Packet state:** `resolved`  
**Date:** 2026-07-10  
**Decision owner:** Product owner  
**Owning current documents:** [Product charter](../design/00-product-charter.md), [rules and content](../design/01-rules-and-content.md), and [project status](../../STATUS.md)  
**Registry approval entry:** Pending stable approver ID
**Supersedes / superseded by:** none

## Resolved decision

- Build a private tool for one client. Public distribution and multi-client operation are not initial requirements.
- Use Archives of Nethys as the sole working rules authority, with a profile retrieval cutoff of 2026-07-10. Do not reconcile against PDFs, printings, or a separate Paizo errata stream.
- Limit the initial Remaster content set to [*Player Core* (AoN 216)](https://2e.aonprd.com/Sources.aspx?ID=216), [*Player Core 2* (227)](https://2e.aonprd.com/Sources.aspx?ID=227), [*Monster Core* (221)](https://2e.aonprd.com/Sources.aspx?ID=221), and [*NPC Core* (236)](https://2e.aonprd.com/Sources.aspx?ID=236). Core encounter rules from other AoN pages may be used when needed to execute that content; this is not a bulk *GM Core* content import.
- The product owner makes the final call on genuinely ambiguous rule interpretations. Agents may propose and implement a provisional or configurable choice, but must keep the ambiguity and selected policy visible and may not promote provisional behavior as supported.
- For rules that explicitly delegate a bounded mechanical choice to the GM, the engine may use a named, versioned policy recorded in saves and evidence. Unbounded narrative judgment must suspend for an explicit ruling when representable or remain unsupported.
- Foundry PF2e data is optional engineering cross-check material only. It is not required and never determines rules truth.

## Why

This boundary keeps the first implementation focused without disguising incomplete or discretionary behavior. It lets agents make progress on candidate mechanics while preserving human control over rules truth and reproducible play.

## Revisit triggers

Create a superseding decision if the tool will be distributed, a second simultaneous client is required, legacy material is proposed, or final rules authority is delegated away from the product owner.

## Resolution status

- [x] Update the owning current documents.
- [x] Add this packet to the decision index.
- [x] Bind the decision to integration commit `fa8e89d3b73373918d6a2a5727da1cd030673cb7`.
- [ ] Add the registry approval entry after selecting the stable approver ID.
- [ ] Create the immutable AoN profile and source records from this accepted boundary.
