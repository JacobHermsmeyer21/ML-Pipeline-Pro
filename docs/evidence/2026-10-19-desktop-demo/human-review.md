# New desktop demo outputs for review

These are the new October 19 outputs, not a recorded human approval. The complete
machine-checkable run passes; usefulness and generated advice still need human
judgment. Original responses and all gate examples remain in [raw.zip](raw.zip).

The real-record inspection says:

> The experiment 0e82cd95-7f59-4bb7-8373-b8012fde26a6 achieved a validation F1 score of 1.0, indicating strong performance. Next, consider comparing this experiment with others using the same dataset to select the best model.

The recorded validation F1 is 1.0 on the small fixture. This does not establish
performance on another dataset. The next response saves a tuning proposal with
the actual dataset/model, validation F1 objective, ten seconds per trial, two
trials and 40 seconds total. The requested demo flag approves its exact hash;
the resulting tuning succeeds and saved proposal replay is identical.

The [generated draft](generated-draft.txt) lists experiments with limit 50 and
offset 0. It passes restricted syntax/API validation, requires review, and was
never executed. Saved replay returns the same draft.

The monitoring interpretation says:

> The window shows a latency issue with a maximum latency of 151.13ms, exceeding the threshold of 100ms. There are 6 seeded latency injections, which could be masking underlying issues. The mean latency is 43.24ms, suggesting normal operation during the window, but the high max latency indicates sporadic performance degradation.

The numeric values match the saved mixed window: 20 measured inferences with five
delays plus one synthetic routing sample. The proposed checks are
`inspect_seeded_delay` and `profile_inference`. The explanation's speculation
about underlying issues or performance degradation is not established by those
measurements. No automatic change occurs.
