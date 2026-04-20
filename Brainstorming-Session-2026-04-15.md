# Brainstorming Session — 2026-04-14/15

## Goal
Build portfolio projects showcasing AI automation of engineering workflows for job search (May 2026+).

## Target Employers (Priority Order)
1. AI-for-engineering startups/Mittelstand — Neural Concept, Monolith AI, SimScale, CADFEM
2. Digital twin / industrial — Siemens Digital Industries, PTC, Hexagon
3. Simulation software — Ansys, Altair, Dassault, Comsol
4. Automotive Tier 1 — lowest priority

## Top 10 Manual Workflows Evaluated

| # | Workflow | Hours/Week | AI Ease | Skill Match |
|---|---------|-----------|---------|-------------|
| 1 | CAD-to-sim preprocessing | 8-15h | High | NXOpen, Simscape |
| 2 | Technical doc parameter extraction | 5-10h | High | NLP/NER, Transformers |
| 3 | FEM post-processing & reporting | 4-8h | High | ParaView, Python |
| 4 | Material data lookup & curve fitting | 3-6h | High | scikit-learn |
| 5 | Design iteration (optimization loops) | 6-12h | Med-High | Topology opt |
| 6 | CAD format conversion | 2-5h | Med-High | NXOpen, Creo |
| 7 | Test data vs simulation validation | 4-8h | Medium | Python |
| 8 | BOM/PLM data entry | 3-6h | Medium | ServiceNow/ETL |
| 9 | Compliance/standards checking | 3-5h | Medium | NLP |
| 10 | Multi-physics coupling & tuning | 5-10h | Low-Med | PINNs |

## Decisions Made

- Focus on simulation/CAE teams (not design, manufacturing, or PLM)
- Pre-processing automation chosen as flagship project (biggest time sink, strongest skill match, most impressive to target employers)
- Post-processing & reporting is a quick-win secondary project
- Surrogate prediction (Neural Concept style) is a separate project

## Projects Planned

| # | Project | Phase | Status |
|---|---------|-------|--------|
| 1 | SimReady — AI pre-processing tool | Design complete | See SimReady-Phase1-Design.md |
| 2 | Surrogate prediction tool (Neural Concept style) | Not started | Separate brainstorming needed |
| 3 | Automated post-processing & reporting | Not started | Quick win, 1-2 weeks |

## Context: OP Mobility Interview
- OP Mobility worked with Neural Concept on car tailgate (3 years traditional simulation)
- Now doing bumpers with Neural Concept for predictions
- They needed someone to set up pre-processing pipeline
- Validates that pre-processing and prediction are two separate roles/tools
- SimReady addresses the pre-processing side, Project 2 addresses prediction side

## Frontend Note
- Starting with Streamlit + PyVista for speed
- React + react-three-fiber considered for future upgrade to show full-stack capability
- Decision: revisit React after Phase 1 is working
