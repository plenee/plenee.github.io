/* The registration invitation, in one place.
 *
 * Every Guide page invites a signed-out reader to register. The wording and the trial length
 * live here and nowhere else, so changing "a free month" means editing this file rather than
 * regenerating every page. That is the whole reason this is a runtime read and not baked in at
 * generation time.
 *
 * Honesty (guide-writing SKILL.md §8): the invitation is about TRYING Plenee, never about what
 * Plenee will do for someone. There are no users yet and therefore no basis for an outcome
 * claim, at any rigor level. Keep this copy about seeing your own numbers — which is true today
 * from the six shipped capabilities — rather than about savings, results or improvement.
 */
window.PLENEE_OFFER = {
  trial: "a free month",
  line: "Plenee is free for your first month — long enough to see your own numbers here instead of somebody's example.",
  cta: "Start a free month",
  href: "https://app.plenee.com/register"
};
