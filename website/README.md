(AI-assisted writeup)

# Emergent Edge explorer

[Explore the cases](https://emergent-edge-case-ai-use-detector.vercel.app/) · [Follow a sample](https://emergent-edge-case-ai-use-detector.vercel.app/pipeline.html) · [About the project](https://emergent-edge-case-ai-use-detector.vercel.app/about.html)

The site opens on the original collection of 30 cases and 12 patterns. The expanded collection contains 51 cases and 10 patterns. They are separate research snapshots, with their original coordinates and assignments preserved.

Select a case to read its summary, evidence, and linked pattern. Pattern labels highlight their cases. The walkthrough follows a selected example through its source, case card, retrieved comparisons, and recorded pattern decision. Prompts and full outputs remain available in expandable sections. These are saved research results; the site does not make live model calls.

Short titles, pattern descriptions, and review notes live in `public/data/display_content.json`, separately from the original research data. Notes identify questionable assignments and distinguish reported experiences, research demonstrations, and defensive proposals. Missing extraction fields are not filled with invented descriptions. Editorial copy does not alter embedding coordinates, saved judgments, or the underlying model outputs.

Serve `public/` for a local preview. The public deployment uses `vercel.json`. Historical standalone URLs redirect to the corresponding working views.
