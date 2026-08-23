# interlinear-sanskrit

Sister project to [greek-reader](https://github.com/hu00yan/greek-reader): an
interlinear reading environment for Sanskrit, reusing the same architecture —
build-time morphological precompute (sandhi splitting + inflectional analysis
frozen into static JSON shards) served by a dependency-free static frontend.
Initial scope: the Bhagavadgītā first, then the principal Upaniṣads, then
Ṛgveda maṇḍala 1–10 via padapāṭha↔saṃhitāpāṭha alignment. Feasibility was
assessed in a per-layer research study (sandhi segmentation, DCS-based
morphology, GRETIL texts, Monier-Williams/Apte dictionaries, public-domain
translations); see `qa-report/` in the greek-reader repository
(`sanskrit-feasibility.md`, `fst-spike.md`) for the evidence base.

**Status: research phase — no pipeline or frontend code yet.**
