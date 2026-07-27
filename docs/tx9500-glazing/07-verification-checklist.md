# 07 — Verification Checklist

This package was assembled from published industry practice and manufacturer
data sheets. **It is not a TORMAX-issued procedure.** Before any of it is used
on a live panel, the items below must be confirmed against TORMAX documentation
and the job shop drawing.

## Why these gaps exist

The TORMAX TX9200/TX9500 installation manual, the TORMAX product pages, the CRL
technical library, and the SpecChem/CGM data sheet PDFs were all blocked by the
network egress policy on the machine this was written on (HTTP 403 at the
proxy). Everything TORMAX-specific below therefore comes from secondary sources
or is left as a variable. Retrieve the primary documents and reconcile.

---

## A — Blocking items (do not pour until all are closed)

| # | Item | Why it blocks | Owner | Status |
|---|---|---|---|---|
| A1 | **Are these rails wet-glaze or dry-glaze?** All-glass door rails ship in both types. Dry-glaze rails use gaskets and wedges and are ruined by cementing. | Cementing a dry-glaze rail destroys the rail and voids warranty | | ☐ |
| A2 | **Does TORMAX approve field/shop cementing of TX9500 rails, and with what product?** Some manufacturers ship panels factory-glazed and void warranty on field glazing. | Warranty and liability | | ☐ |
| A3 | **Which Por-Rok is actually on the shelf** — regular or Super? Brand (CGM vs SpecChem)? TDS revision? | The two products have opposite restrictions. See [02](02-material-selection.md) | | ☐ |
| A4 | **Are these panels interior or exterior/weather-exposed?** | Determines whether regular Por-Rok is usable at all | | ☐ |
| A5 | **Glass bite `B`** from the TORMAX drawing | Every dimension in this package depends on it | | ☐ |
| A6 | **Rail internal channel width `Wc`** and resulting `Cs` | Determines setting block and cement geometry | | ☐ |
| A7 | **Setting block thickness `Sb`** specified by TORMAX | Sets the cement bed depth under the glass edge | | ☐ |
| A8 | **Hanger/carrier fastener torque** and whether bosses bear on the glass edge | Structural; guessing torque on a hanging panel is not acceptable | | ☐ |

---

## B — Important but non-blocking

| # | Item | Owner | Status |
|---|---|---|---|
| B1 | TORMAX-specified cure time before the panel may carry load. This package recommends 24 hr; confirm TORMAX does not require longer | | ☐ |
| B2 | End cap depth `d` for the dam setback | | ☐ |
| B3 | Whether the rail interior is mill aluminum, anodized, or clad — affects isolation coating decision | | ☐ |
| B4 | TORMAX-approved sealant for the cap bead (neutral cure assumed) | | ☐ |
| B5 | Panel weight `Wp` range the iMotion 2301/2401 operator is set up for — glazing adds cement weight | | ☐ |
| B6 | Breakout panel geometry, if these are breakout panels — pivot hardware in the rail changes the fill zone | | ☐ |
| B7 | Whether the TX9500 rails have internal ribs/serrations for cement keying (changes fill volume calc) | | ☐ |
| B8 | Local code requirements for glazing in an automatic entrance (ANSI/BHMA A156.10) | | ☐ |

---

## C — Documents to retrieve

Retrieve these from an unrestricted connection and file them alongside this
package:

- [ ] TORMAX TX9200/TX9500 Installation & Service Manual
      — `https://d3eu1jnerk19h.cloudfront.net/documents/products/TX9200-TX9500-TCP-Slide-Manual-V-2-11-2-09.pdf`
      — mirrors: `absupply.net/pdf/Tormax_TX9200 Manual.pdf`,
        `addisonautomatics.com/wp-content/uploads/manuals/tormax/SLIDER I MOTION.pdf`
- [ ] TORMAX TX9000 slider parts catalogue
      — `addisonautomatics.com/wp-content/uploads/manuals/tormax/TX9000 SLIDER PARTS CATALOG.pdf`
- [ ] TORMAX drawings / specifications / brochures index
      — `https://www.tormaxusa.com/en/81/drawings-specifications-brochures`
- [ ] Job-specific TORMAX shop drawing for these panels
- [ ] Data sheet for the exact Por-Rok bucket in the shop
- [ ] Setting block and sealant data sheets

## D — People to call

- [ ] **TORMAX USA technical support** — San Antonio, TX. Ask specifically:
      "For TX9500 all-glass sliding panels, are the rails wet-glaze or
      dry-glaze, what glazing compound do you approve, what is the glass bite,
      and what is the required cure time before the panel is hung?"
- [ ] **The glass fabricator** — confirm glass sizes were cut to the *actual*
      rail heights and bite, not catalogue values.
- [ ] **Por-Rok technical line** (CGM Building Products or SpecChem, per your
      bucket) — confirm suitability for a confined aluminum glazing channel in
      contact with tempered glass. Anchoring cement is marketed for anchoring
      bolts and railings into concrete; a door rail is an adjacent but not
      identical application, and it is worth ten minutes on the phone to have
      the manufacturer say yes.

---

## Sign-off

```
  ┌────────────────────────────────────────────────────────────────────┐
  │  This procedure is released for production use on job ___________  │
  │                                                                    │
  │  All Section A items closed        ☐    Date ____________________  │
  │  Section B items closed or waived  ☐    Date ____________________  │
  │  Section C documents on file       ☐    Date ____________________  │
  │                                                                    │
  │  Variable table in 01 completed from shop drawing   ☐              │
  │                                                                    │
  │  Released by ______________________  Title ______________________  │
  │  Signature ________________________  Date _______________________  │
  └────────────────────────────────────────────────────────────────────┘
```
