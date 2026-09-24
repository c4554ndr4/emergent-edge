(AI-assisted writeup)

# Emergent Edge explorer

[Explore the cases](https://emergent-edge-case-ai-use-detector.vercel.app/) · [Follow a sample](https://emergent-edge-case-ai-use-detector.vercel.app/pipeline.html) · [About the project](https://emergent-edge-case-ai-use-detector.vercel.app/about.html)

One collection brings together 71 case cards and 19 patterns. Repeated cases appear once. Select a case to read its summary, evidence, and linked pattern, or select a pattern to highlight its cases.

The walkthrough contains 34 saved recordings covering 33 cases. It follows the source, extracted case card, retrieved comparisons, and recorded pattern decision. Each recording retains its own prompts and batch context. One case has two recordings, both available in the sample selector. The site does not make live model calls.

The combined map aligns the two saved layouts using their ten shared cases. This is an approximate display alignment, not a newly computed embedding projection or a quantitative measure of distance between the research runs. Pattern stars sit at the center of their displayed cases. Original files and alternate case analyses remain available; combining the views does not rerun the judges or change their decisions.

Short titles, pattern descriptions, and review notes live in `public/data/display_content.json`. Notes identify questionable assignments and distinguish reported experiences, research demonstrations, and defensive proposals.

Run `python3 scripts/combine_collections.py` to rebuild the combined data from the saved public snapshots. Serve `public/` for a local preview. The deployment uses `vercel.json`; older collection URLs lead to the unified explorer.
