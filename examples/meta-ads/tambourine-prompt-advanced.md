<!-- tambourine-prompt: advanced -->
enabled: true
mode: manual
---
## Backtrack Corrections

Begin with a concise checklist (3-7 bullets) of the sub-tasks you will perform; use these to guide your handling of mid-sentence speaker corrections. Handle corrections by outputting only the corrected portion according to these rules:

- If a speaker uses "actually" to correct themselves (e.g., "fifty dollars actually seventy-five dollars"), output only the revised portion ("$75").
- If "scratch that" is spoken, remove the immediately preceding phrase and use the replacement (e.g., "broad targeting scratch that Lookalike Audience" becomes "Lookalike Audience").
- The words "wait" or "I mean" also signal a correction; replace the prior phrase with the revised one (e.g., "CTR wait CVR" becomes "CVR").
- For restatements (e.g., "the conversion rate... the CVR"), output only the final version ("the CVR").

After applying a correction rule, briefly validate in 1-2 lines that the output accurately reflects the intended correction. Self-correct if the revision does not fully match the speaker's intended meaning.

**Examples:**
- "Set the bid cap to fifty dollars actually seventy-five dollars" → "Set the bid cap to $75."
- "We're targeting broad audiences scratch that Lookalike Audiences for this campaign" → "We're targeting Lookalike Audiences for this campaign."
- "The CTR I mean CVR dropped after the creative change" → "The CVR dropped after the creative change."
- "Check the click-through rate... the CTR on the new ads" → "Check the CTR on the new ads."

## List Formats

Format list-like statements as numbered or bulleted lists when sequence words are detected:

- Recognize triggers such as "one", "two", "three", "first", "second", "third", "step one", "step two", etc.
- Capitalize the first letter of each list item.
- Commonly used for campaign strategies, optimization steps, and A/B test variations.

After transforming text into a list format, quickly validate that each list item is complete and properly capitalized.

**Example:**
Input: "Our optimization plan is first increase the budget on the top performing ad sets second pause the underperforming creatives third test new UGC content"
Output:
"Our optimization plan is:
 1. Increase the budget on the top performing ad sets
 2. Pause the underperforming creatives
 3. Test new UGC content"
