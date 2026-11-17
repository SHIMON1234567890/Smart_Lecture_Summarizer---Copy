Lectures: 20 (TIB test split, seed 42, transcripts up to 6,000 words); transcripts 3782 words on average, reference abstracts 163 words.

| system | words | ROUGE-1 | ROUGE-2 | ROUGE-L | BERTScore |
|---|---|---|---|---|---|
| Lead-200 (first 200 words) | 200 | 0.288 (0.255–0.317) | 0.044 (0.034–0.054) | 0.136 (0.122–0.149) | 0.746 (0.735–0.756) |
| App summarizer (full) | 368 | 0.265 (0.226–0.303) | 0.043 (0.034–0.054) | 0.125 (0.111–0.141) | 0.761 (0.751–0.771) |
| App summarizer, first 200 words | 187 | 0.304 (0.267–0.338) | 0.047 (0.036–0.059) | 0.145 (0.131–0.159) | 0.764 (0.755–0.773) |

Difference vs Lead-200 on the same lectures (mean, 95% CI, lectures won):

- App summarizer (full): rouge1 -0.023 (-0.047 to +0.000), wins 7/20; rouge2 -0.001 (-0.013 to +0.011), wins 8/20; rougeL -0.011 (-0.019 to -0.002), wins 6/20; bertscore +0.016 (+0.008 to +0.023), wins 15/20
- App summarizer, first 200 words: rouge1 +0.016 (-0.013 to +0.044), wins 12/20; rouge2 +0.003 (-0.011 to +0.019), wins 8/20; rougeL +0.010 (-0.003 to +0.023), wins 11/20; bertscore +0.018 (+0.010 to +0.027), wins 16/20
