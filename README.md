# Case Companion

A local Indian legal case-building prototype for Kuku Problem 2. It turns an out-of-order account into a reviewable timeline, requires confirmation, shows numbered legal source panels, explores hypothetical challenges, and creates formal Word drafts.

## Assignment submission

- [Two-page solution report](submission/solution.pdf)
- [Raw outputs folder](submission/raw-outputs/) and [downloadable ZIP](submission/raw-outputs.zip)
- [Case-by-case results](submission/raw-outputs/Results%20summary.md)

The evaluation used the supplied 20 fictional scenarios. The archived report reflects the evaluation build. This checkout also contains the subsequent same-day timeline and consumer-review stage fixes.

## Run

Requires Python 3.10+ and a modern browser. Start from the repository root. The base app uses the standard library. Run `python -m pip install --target .deps -r requirements-pdf.txt` from the app directory to enable PDF previews with the pinned parser.

```powershell
python server.py
```

Open the localhost address printed in the terminal, then choose **Sign in**, **Create account**, or **Continue as guest**. Select **Try a sample**, then **Organise my story**. Review and confirm the structured account. On the legal screen, choose where the matter stands and select **Explore relevant laws**. The fictional sample uses scripted analysis and guided practice.

## Live AI

Copy `.env.example` to `.env`, set `LAWYER_API_KEY`, and restart. The example uses `openai/gpt-oss-120b` through OpenRouter at `https://openrouter.ai/api/v1`. `LAWYER_MAX_TOKENS=3000` caps each completion. Store credentials in the ignored local `.env` file. [OpenRouter model API](https://openrouter.ai/openai/gpt-oss-120b/api)

Live mode can return provider, quota or validation errors. The 20-case archive includes the original attempts and any retries.

OpenAI and Gemini can also be configured through their compatible endpoints. Previous keys returned insufficient quota (OpenAI) or temporary unavailability (Gemini). No automatic provider fallback is used. A local compatible server can be used with an HTTP localhost base, model name, and `LAWYER_LOCAL_MODEL=1`.

Guest mode defaults to local extraction and reference search. Select **Use live AI** before organising the story to opt in for that case. Live calls can send the story, pasted evidence, relevant selected PDF passages, and statute excerpts to the provider. OpenRouter requests require Zero Data Retention routing and deny provider data collection. OpenRouter account-level prompt logging and broadcast settings are managed separately. [OpenRouter data retention controls](https://openrouter.ai/blog/insights/zero-data-retention/) · [OpenRouter logging information](https://openrouter.ai/support)

## Host the reviewer demo

The hosted build runs the existing case workflow in one Waitress process behind managed HTTPS. It accepts guest sessions and disables both account endpoints and provider calls. No account database, persistent disk or API key is required. Active cases expire after 30 minutes of inactivity and clear when the process restarts. Reviewers can use the sample or enter fictional facts, and can save the generated Word draft or encrypted chat file on their device.

1. In Render, create a **Blueprint** from this repository. [Blueprint setup](https://render.com/docs/infrastructure-as-code)
2. Review the compute plan before activating it. The supplied `render.yaml` selects Starter for a review link that stays awake between visits. Select Free if a cold start is acceptable. [Render service behavior](https://render.com/docs/faq)
3. Render installs `requirements-hosted.txt`, starts `hosted.py`, and checks `/healthz`. The public origin defaults to Render’s assigned HTTPS host. For a custom domain, set `CASE_COMPANION_ORIGIN` to its exact HTTPS origin without a trailing slash. Keep the service at one instance while sessions live in process memory. [Render web services](https://render.com/docs/web-services)
4. Open the actual HTTPS URL in an incognito window. Follow **Continue as guest → Try a sample → Organise my story**, confirm the account, open a legal citation, and check that the exported Word document opens. Repeat with a different fictional input and submit the tested HTTPS URL.

To test the guest build locally, install the hosting dependencies with `python -m pip install --target .deps -r requirements-hosted.txt`, put `.deps` on `PYTHONPATH`, and run `python hosted.py`. It binds to loopback when no public origin is configured. Stop the local server first or choose another `PORT`.

For Railway, use Railpack with `requirements.txt` and set the start command to `python hosted.py` if the service has a dashboard override. Set `/healthz` as the deployment health check and use one replica. The app uses `RAILWAY_PUBLIC_DOMAIN` to select the HTTPS origin and listens on Railway's `PORT`. [Railway build and start commands](https://docs.railway.com/builds/build-and-start-commands)

## Workflow and limits

1. Submit a story with optional evidence text, a labelled `.txt` file, or a text PDF. PDF extraction runs in a short-lived local worker. Preview the text and select up to eight pages. Live intake and analysis each receive excerpts of up to 1,600 characters from up to five relevant selected pages. Click references such as `[D1 p.2]` to check the extracted passage and its page number. Image-only scans still need a manually pasted passage. Use **Anything to correct or add?** and confirm the revised timeline when facts change.
2. Review and confirm the timeline. Write dates and times as you would normally say them. The timeline groups events by day, orders stated times within a day and preserves clear relative timing such as “that evening.” A day can appear without a calendar date. Use the correction field in your own words when something is unclear. On the next screen, select the latest procedural step for guidance tailored to that stage. Contradiction detection is model-assisted in live mode. Evidence remains unverified.
3. Legal retrieval searches **33 selected national provisions**. It combines exact terms, curated everyday-language phrases, and optional topic labels inferred by the live intake model. Selected procedural questions can add consumer procedure, BNSS section 173, or BSA section 63 candidates. Applicable-date filters exclude newer provisions when all known event dates predate their commencement. Mixed or unknown dates and proceedings already underway need transitional-law review. State-specific sources and older IPC provisions remain outside the collection.

Missing CCTV, receipts or witnesses does not block issue spotting. Section relevance and proof are separate: a match means the section may fit the reported description, not that guilt is established. Results are grouped as **possible starting points from the account**, **conditional sections to revisit if more facts emerge**, and (in live mode) **less likely on the facts shared**. Each provision has a source-checked issue summary, when-to-use condition, limits and helpful facts to clarify. For food, property, BNS sexual-offence and POCSO provisions, the model selects from curated excerpts while the app supplies source-checked meanings and boundaries. This supports progressive case-building: an initial account can identify a route, and later details can make a distinct remedy, safeguard or offence relevant. It does not prove a claim or guarantee that all laws are covered. Sexual-offence/child-safety users are asked to avoid identifying or graphic details; live AI still sends submitted text to the configured model after consent. Factual practice scenarios and next steps use conservative templates to avoid invented burden-of-proof or procedural claims. These templates are English; multilingual fidelity still needs testing.
4. Source IDs, duplicate references, output structures and support labels are validated in code. Numbered law panels use the official source metadata, stored excerpts and reviewed application wording. Live AI may select and rank retrieved IDs. Its free-form legal prose is discarded before display. If a proposal contains an unavailable citation the app blocks it. If no reviewed source matches, the app states the coverage gap instead of supplying a provision. Source snapshots, later amendments, jurisdiction and actual applicability still need legal review.
5. Choose a hypothetical and write a short practice answer. The app provides a guided answer structure using application-authored wording in both modes. Practice answers do not change the confirmed timeline or enter the document draft. Supporting and adverse decisions, court hierarchy, later treatment and applicability require verification before relying on precedents.
6. Draft generation is deterministic. Choose the format based on the recipient and what you want them to do. Add the material facts separately and list only the documents actually attached. The timeline can be copied into that field for editing. The app leaves dates, forums, amounts and procedural details for confirmation before use.

## Word templates and PDF

The **Drafts** screen provides eight formats. The same matter can need several different documents.

| Intended next step | Format and information to confirm |
| --- | --- |
| Ask a private party to fix a problem or pay an agreed balance | **Legal notice** or **Payment demand notice**. Record the agreement, amount and credits if relevant, exact demand, prior communications and proposed service. Confirm the response period separately. |
| Answer a private notice | **Reply to notice**. Identify the original notice, receipt date, disputed paragraphs, position on each and any proposed resolution. |
| Ask a consumer commission for relief | **Consumer commission complaint**. Confirm the commission, parties and roles, transaction, cause of action, jurisdiction, limitation, relief and attachments. The draft includes verification wording. Check the separate case uploads in the [e-Jagriti filing guide](https://e-jagriti.gov.in/static/media/CC_Filing.34e0fc5dd03b1d864cab.pdf). |
| Give information to a police station | **Written police complaint**. Confirm the officer, date, time and place, what the informant observed, people and records, and the requested action. The [BNSS reporting provision](https://www.ncrb.mha.gov.in/uploads/SankalanPortal/ChaptersBNSS.html#173) governs the applicable reporting process. |
| Report suspected unsafe food | **Food safety grievance**. Include the business, order, identifiable food items or batch, symptoms, relevant records and request for investigation or inspection. [FSSAI Food Safety Connect](https://foscos.fssai.gov.in/consumergrievance/faqs) |
| Prepare to discuss a possible civil suit | **Civil plaint for advocate review**. Confirm the court, cause of action, jurisdiction, valuation, court fee, limitation, applicable property details, relief and verification. [Code of Civil Procedure, Order VII](https://www.indiacode.nic.in/bitstream/123456789/2191/1/eng.pdf) |
| Clarify a disputed, specialised or already filed matter | **Case brief**. Record parties, evidence, disputes, known deadlines and questions to take to an advocate. |

In the fictional scenario pack, Cases 2 and 3 illustrate the difference between a food grievance and a consumer compensation complaint. Cases 6 and 7 may involve private notices or replies. Case 8 can use a civil plaint outline for consultation. Cases 11, 12 and 17 need the amount, due date and any limitation issue checked before using a payment demand. Cases 4, 5, 9, 10, 13, 14, 15 and 18 are better starting points for a brief or a specialist review of an existing notice or order. In Case 16 use only truthful facts and genuine records. In Case 19 seek immediate safety assistance before preparing documents. In Case 20 review the cancellation terms before making a demand or choosing a forum. For Case 1, use a police complaint for initial reporting and a case brief to review the already-filed complaint and other routes.

A private notice format does not substitute for a statutory notice or an advocate-reviewed filing. A dishonoured-cheque demand, for example, has specific requirements for the amount demanded. [Supreme Court decision on section 138 demand notices](https://api.sci.gov.in/supremecourt/2024/24253/24253_2024_1_1501_64452_Judgement_19-Sep-2025.pdf)

Default export uses A4, Times New Roman 12 pt, 1.5 line spacing and one-inch margins. Font and size are selectable. Upload a static `.docx` under 1 MB with exactly one paragraph containing `{{CASE_DRAFT}}`. The exporter preserves supported formatting, including the marker paragraph's direct run and paragraph settings. Templates containing external links, dynamic fields, macros or embedded objects are rejected. Default document text is English.

Download an editable DOCX or use **Print / save as PDF** with the browser. The browser print uses the selected font; an uploaded Word template affects DOCX only. No automatic PDF renderer is bundled.

## Reuse and attribution

The grounding contract in `vendor/upstream_prompt.py` is adapted from [Nyaya Mitra](https://github.com/rishikeshbeliya/nyaya-mitra), commit `3e72f2b25610312d0fcc4a6ca6bdb781b23e2b2a`, copyright 2025 Rishikesh Beliya, MIT. Its license is retained in `vendor/NYAYA_MITRA_LICENSE`. We replaced its Streamlit/Qdrant/LangChain runtime with a standard-library server and added the confirmed case workflow, UI, citation panels, validation, scenario view and document export.

LawyerLens's separation of user documents and legal sources and Mike aur Donna's case/evidence-gap presentation informed the design; no source code from those repositories was copied. No code was copied from the Java project or Niyam SahaAI. Do not claim the upstream grounding design as original work.

## Court examples and judgment datasets

After confirming a case, look for **Court decisions to compare** at the top of Legal review. It matches the confirmed facts to a selected library of Supreme Court decisions. Each suggestion links to the official decision and explains the ruling, why it came up, what differs, and what to prepare. The box also links to BNSS section 173 or Consumer Protection Act section 35 where relevant. Choosing a later procedural stage brings hearing-related examples forward. Suggestions work locally and are included in the encrypted chat export.

Four examples also appear in numbered law citations for property, consumer housing, child protection and food testing. Later case history has not been comprehensively checked. Run `python scripts/add_research_sources.py` after rebuilding the base catalogue with `scripts/expand_sources.py` to reattach those examples.

- [High Court dataset](https://github.com/vanga/indian-high-court-judgments): CC-BY-4.0 dataset, metadata-first court/date filtering; avoid bulk ingestion for a short prototype.
- [Supreme Court dataset](https://registry.opendata.aws/indian-supreme-court-judgments/): CC-BY-4.0; registry reviewed on 18 November 2026. Its description lists 1950–2025 coverage. Dataset access alone does not establish current precedent status.

The bulk datasets remain external. The app uses the curated examples and links directly to the official decisions.

## Privacy and deployment

Registered accounts use a username and password. The local SQLite database stores usernames and salted scrypt hashes in the ignored `.accounts` directory. Usernames are case insensitive. Guest and registered case workspaces both expire and use encrypted case files to resume later. The database stores no case history.

The evidence plan appears in Legal review after the account is confirmed. For a reported physical incident it highlights relevant timeline entries, asks about viewpoint and changes at the scene, and suggests records to preserve or request safely. It adapts to the reported issue and procedural stage. It gives preservation guidance for the user; scene examination and physical collection belong with trained authorities. The checklist is generated locally and appears in the encrypted conversation export.

The timeline includes a **Fact-to-evidence map** and one suggested clarification at a time. A PDF link means the timeline cites that selected page or the page has overlapping text. Open the excerpt and check what it actually establishes. Answering or skipping a question records that choice for the session and the encrypted case file. A follow-up compares events and selected PDF pages. The next legal review compares its law list and next steps with the previous review, including whether the reported case stage changed.

Law cards use reviewed notes from the source catalogue. For core consumer and theft provisions, the citation detail includes exact excerpts from the stored statute. Live review can also propose pairs of claims and statutory passages. The app shows a pair only if the claim matches the displayed source wording and the passage occurs verbatim in the catalogue, ignoring layout whitespace. Date and stage notes help flag applicability questions. These checks do not establish legal applicability, authenticity of evidence, or later treatment of a judgment.

**Download entire chat** creates a password-protected `.casecompanion` file in the browser. It contains the conversation, previous analyses and practice responses, drafts, the latest timeline and selected PDF excerpts. The browser encrypts it with AES-GCM using a password-derived key. Keep the file and password secure. **Import previous chat** opens the file in a new guest session, replaces the workspace and restores the conversation and timeline locally. It requires fresh confirmation before legal analysis and fresh consent before a follow-up can use the model. Add new facts under **Anything to correct or add?**. Original PDFs and Word templates are separate files. Historical drafts and analysis remain visible in **Case conversation**.

The server binds to 127.0.0.1, checks Host/Origin, and requires a random per-tab guest token and the case ID to access case data. Guest tokens, case material, PDF previews and drafts live in memory. The app disables caching and does not write case history or request logs. **Clear case** removes the current case. **End guest session** clears the browser workspace and deletes its server records. Closing or reloading the page requests the same cleanup when the browser can deliver it. Otherwise, a background task removes inactive guests and their cases after 30 minutes without an app request, with a 15-second sweep interval. A restart also clears all sessions. Downloaded files remain on the device. This is a local guest workspace. Any public deployment requires separate security review.

PDF preview uses a separate process with a timeout and limited concurrency. The worker receives no provider credentials and returns page text. Model requests reject redirects and cap response sizes. The encrypted case file is the browser's full conversation export. Word drafts are ordinary local files and need the same handling as other legal documents.

## Test and raw outputs

```powershell
python -m unittest discover -s tests -v
python scripts/evaluate_research.py
python scripts/evaluate_research.py --live
```

The [submission outputs](submission/raw-outputs/) include original intake and legal reviews, provider errors, retries, and the original editable Word draft exports.
