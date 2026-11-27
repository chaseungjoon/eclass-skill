# eClass commands

Run with `python3 "{baseDir}/scripts/eclass.py"` followed by one of these commands. `{baseDir}` is the skill folder. Outside an agent, run the script by its path with `CANVAS_BASE_URL` and `CANVAS_API_TOKEN` set in the environment or in `~/.config/eclass/config`.

| Request | Example arguments |
|---|---|
| Check the connection | `check` |
| Find the course ID for a keyword | `courses --search "머신러닝"` |
| Find older courses | `courses --term all --limit 100` |
| Outstanding assignments in the next two weeks | `planner --kind assignment --unsubmitted --days 14` |
| Course items for a specific period | `planner --course COURSE_ID --start YYYY-MM-DD --end YYYY-MM-DD` |
| Outstanding assignments even without a deadline | `assignments COURSE_ID --unsubmitted` for each relevant class |
| Canvas-flagged missing work | `missing` |
| Exam announcements | `announcements --days 45 --search "기말" --body --limit 10`, and repeat with an English title term if needed |
| More detail on one notice | `announcement COURSE_ID TOPIC_ID`, using the IDs from the list |
| Calendar event details | `calendar --course COURSE_ID --days 30 --body --limit 10` |
| Submission status in a course | `assignments COURSE_ID --limit 50` |
| Assignment instructions, your score, and posted feedback | `assignment COURSE_ID ASSIGNMENT_ID` |
| Calculated course scores | `grades` or `grades --course COURSE_ID` |
| Syllabus | `syllabus COURSE_ID` |
| Module list and contents | `modules COURSE_ID`, then `modules COURSE_ID --module MODULE_ID` |
| Available course file titles and links | `files COURSE_ID` |

The default term is the latest regular semester (names like `2026년 1학기`, `2026-2`, or `Fall 2026`) in the enrolled course data whose start date has arrived. If no term name looks like a regular semester, the latest started term is used. Use `--term` for another semester, including winter or summer sessions, or `--course` for a known ID. A course can remain visible long after the end of the term. The term dates are included with each course when Canvas supplies them. Partial course and title matches are case-insensitive. Adding `--body` to an announcement or calendar search also checks its full plain-text body.

Dates and timestamps are interpreted in Korea time. Ranges include both dates. `--days` includes today and looks backward for announcements and forward for the planner and calendar. The planner unsubmitted filter uses Canvas assignment flags. The course assignment unsubmitted filter uses the student's submission state and skips gradebook-only entries that have no submission type. Canvas's missing-submissions view can include offline work such as presentations and can differ from a date-based overdue query. Check the actual submission type for ambiguous cases.

List commands return `matched`, `shown`, and `items`. Dates and course context are included where applicable. Raise `--limit` to at most 100 or narrow the query when more records match. Canvas responses are followed through their pagination links. Body excerpts include a `truncated` flag. Open the original Canvas page for attachments, rich formatting, or the full body.

Calendar events and assignment deadlines are separate Canvas data. The planner covers course items and the calendar command covers course events. Announcements often contain exam dates, cancellations, attendance links, and deadlines that instructors did not add as calendar events. For exam questions, search announcements from the semester start through today with `--body` and plausible Korean and English terms such as `기말`, `시험`, and `final exam`. Review less explicit notices if those searches are inconclusive and report when the date is unavailable.

Course total scores are Canvas calculations and can be null even when individual assignment grades are visible. Many Korean universities run weekly learning, lecture videos, and attendance in an external tool that is only available in the web interface. Some schools restrict the course Files endpoint (HTTP 401), and some syllabus information may live in an external tool. The helper reports restricted APIs and provides first-party links where available.

[Canvas REST API reference](https://developerdocs.instructure.com/services/canvas/resources)
