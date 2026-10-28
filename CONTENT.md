# Editing the About, Contact, FAQ and Testimonials pages

Everything below is edited in the Django admin. No code or deploy is needed, and changes appear on the site **immediately**.

## First time only
```
python manage.py migrate
python manage.py seed_pages      # creates the four pages from today's text and fills blank contact details
```
Safe to re-run: it never overwrites anything you have edited. (Even without it the pages still work: they show built-in default text.)

## Admin > Page content (one record each for About, Contact, FAQ, Testimonials)
| Field | What it does |
|---|---|
| Small label / Title / Intro sentence | The text in the banner at the top. Blank = the default. |
| Header photo | The banner background. Upload a wide photo (2000 x 800 px is ideal, JPG/PNG/WebP, under 6 MB; narrower than 1000 px is rejected as it would look blurry). It is **optimised automatically** into 2-3 small WebP sizes so phones download about 25 KB instead of megabytes. Blank = the default photo. |
| Which part of the photo to keep | Where the photo is cropped on narrow screens, e.g. `50% 30%` (left-right, top-bottom) or `center top`. |
| Main text | The body text. Blank line = new paragraph. |
| Side photo + description | About page only. Write a description of the photo for screen readers. |
| Extra sections | Any number of headings with text. Start a line with `- ` for bullet points. Tick **Highlight box** for a tinted notice (used for "Staying safe when you pay"). Untick **Is active** to hide one without deleting it. |

## Other places
* **Admin > Company profile**: phone numbers (one per line), email, address, short location, opening hours, map link, registration number, certifications. These feed the **top bar, footer, Contact page, About page, Privacy, Terms and every call-to-action**, so you change them once.
* **Admin > FAQs**: add questions, reorder with the Sort order column, untick Published to hide. The Google "FAQ" markup updates by itself.
* **Admin > Testimonials**: a testimonial only appears when both **Published** and **Consent given** are ticked.

## How it stays fast
Each page's content is read from the database once, then served from the cache (10 minutes, `CONTENT_CACHE_SECONDS`), so a normal visit costs **zero** database queries for this content. Saving anything in the admin clears the cache at once. One caveat: edits made with raw SQL or Django's bulk `.update()` do not clear it; they appear within 10 minutes (or restart the app).
With several server processes use Redis (`REDIS_URL`) so they all see the clear immediately.
