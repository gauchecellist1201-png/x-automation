# CORE Social OS

Review-first drafts to the owner's LINE. This repository does not publish to X or LINE OpenChat.

- Every day: three X draft messages for manual selection and posting.
- Monday: one OpenChat draft with practical guidance and, when available, up to three recent article headlines and links. Read the articles before reposting them.
- No paid AI API, X API, or external scheduling service. The existing LINE Messaging API push uses GitHub Secrets `LINE_CHANNEL_ACCESS_TOKEN` and `LINE_USER_ID`.
- The workflow uses GitHub Actions schedules. These can be delayed, so the 08:07 JST daily and Monday 08:22 JST weekly starts are targets rather than exact delivery guarantees.
- Only one recipient is configured. Three bubbles in one request count as one push recipient; check the LINE plan's current free-message allowance before adding recipients.

To check locally: `python -m unittest discover -s tests -v`. To run manually in Actions, select **CORE Social Drafts** → **Run workflow** and choose `daily` or `weekly`. A manual rerun for the same day uses LINE's deterministic retry key to avoid duplicate delivery. Do not put credentials, client records, or unpublished case details in this public repository.

To improve draft quality, edit the public `IDEAS` list in `social.py` using anonymized lessons from Obsidian. The private `core-knowledge` repository is intentionally not copied into public Actions logs or source. Review the weekly reference headlines and the X text before posting. Record impressions, profile visits and follows each week to decide which topics to retain.
