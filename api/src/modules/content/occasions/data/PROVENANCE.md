# Calendar snapshots

The catalogue is a source snapshot, not a claim that every informal observance
in every country exists in a universally complete calendar. The default `youth`
selection announces at most three explicitly curated events. Unlisted government,
administrative, religious and historical dates stay in the underlying catalogue
and are omitted from that output. An empty selection stays empty; there is no
fallback to administrative dates. Explicit `all` selection returns every matching
entry from the selected categories without this editorial cap. Category switches
and exclusions apply in both modes; custom entries are included independently of
category switches and have first priority within the youth cap.

* `events.json`: unmodified CC0-1.0 data from
  https://github.com/persian-calendar/events/blob/3bfbcc5b667765691784b55b58d8a385217d96d9/events.json
  (641 entries). `CC0-1.0.txt` is the upstream license. The snapshot identifies
  Tehran University's official 1405 calendar as the Iranian catalogue source.
* `iran_lunar_months.txt`: unmodified CC0-1.0 data from
  https://github.com/roozbehp/qamari/blob/575d275ef169c0a18012506d473ba1008a1c10d0/consolidated.txt
  (2194 Iranian month starts). Asterisks are observation corrections, not
  uncertainty markers. Only factual dates are used, with no Saudi or arithmetic
  fallback. Missing coverage is returned as a visible warning.
* `iran_lunar_1405.json`: 13 factual month starts independently transcribed from
  the official final Tehran University calendar, extending coverage through
  2027-03-20. Original source:
  https://calendar.ut.ac.ir/documents/2139738/7092644/Calendar-1405.pdf
  Public mirror used when the original server blocked automated access:
  https://www.scribd.com/document/990789768/Calendar-1405
  Dates are facts; neither PDF text nor calendar conversion code is copied.
  The last month is partial: no month-end date is inferred beyond the documented
  year. Dates remain subject to subsequent official lunar sighting corrections.
* `supplement.json`: 48 independently recorded rules with original Persian
  titles and no copied source prose: World Habitat Day and World Architecture Day
  from UN sources, plus 46 informal social, relationship, internet and fun dates
  across all 12 months. Source URLs, regional context and an explicit unofficial
  status accompany every informal entry. The organizers' sites verify Emoji,
  Star Wars, Towel and Talk Like A Pirate dates; Fulton County's own event verifies
  Girlfriend Day; remaining recurring dates were checked against the stated
  date-change rule on each linked National Today catalogue page on 2026-10-05.
  These catalogue dates do not establish government or UN recognition. The
  October 5 No Prostitution entry is an explicitly identified civil campaign,
  documented in a 2002 campaign publication; current worldwide observance is not
  claimed. Girlfriend Day includes the platonic female friendship meaning, too.
  Halloween already exists upstream and is not duplicated. Taco Day is omitted
  because published dates conflict following a campaign schedule change.
* `youth_selection.json`: 81 editorially selected, stable content IDs from the
  existing verified snapshots, with explicit priorities and reasons. No new dates
  or factual observance claims are introduced. It includes the 46 informal social,
  relationship, internet, food and fun entries, plus a deliberate subset of
  science/programming, music/art/books, mental health, equality and environment
  days, and Nowruz, Yalda, Sizdah Bedar, Chaharshanbe Suri and Sepandarmazgan.
  Overlapping catalogue versions of the same cultural festival are not selected
  twice. Lower priority numbers appear first; equal priorities use the stable ID
  as a deterministic tie-break. Maximum output defaults to three and can be set
  from one to five. Adding a catalogue category or an entry does not automatically
  make it eligible. Changing the editorial selection never changes source IDs,
  factual titles, sources, status, notes or calendar matching rules.

Rule interpretation: upstream weekdays use Sunday=1 through Saturday=7.
`nth day from` is inclusive (January 1 is day 1). Weekday offsets apply after
finding the designated weekday. One-off events only appear in their stated year.
Black Friday's upstream rule/title is corrected at lookup to the Friday following
the fourth Thursday of November; it is not always November's last Friday.
The original identity is retained to preserve configured exclusions.

Snapshots were retrieved on 2026-10-05. To refresh, pin new commits, verify source
and license, update coverage and regression tests, and retain stable event IDs
when only metadata changes. Runtime lookup needs no network.
