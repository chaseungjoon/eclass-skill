#!/usr/bin/env python3
"""Read student-facing Canvas LMS (eClass) data and print compact JSON.

Configure with CANVAS_BASE_URL and CANVAS_API_TOKEN, either as environment
variables or as KEY=VALUE lines in ~/.config/eclass/config (override the path
with ECLASS_CONFIG). Environment variables take precedence.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime, time as clock_time, timedelta, timezone
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


ORIGIN = ""  # set from CANVAS_BASE_URL at startup, e.g. https://eclass.example.ac.kr
HOST = ""
API = "/api/v1/"
KST = timezone(timedelta(hours=9), "KST")
MAX_PAGES = 20
NEXT_PAGE = re.compile(r'<([^>]+)>\s*;\s*rel="?next"?(?=[,;\s]|$)')
# Regular semesters as Korean universities usually name them: "2026년 1학기",
# "2026-1학기", "2026-2", "2026 Spring", "Fall 2026", "2026년 가을학기".
REGULAR_TERM = re.compile(
    r"(?i)\d{4}\s*년?\s*[-./]?\s*[12]\s*(학기)?"
    r"|\d{4}\s*년?\s*(봄|가을|spring|fall|autumn)\s*(학기|semester)?"
    r"|(spring|fall|autumn)\s*(semester)?\s*\d{4}"
)
DEFAULT_TERM = re.compile(r"(?i)default\s*term|기본\s*학기")
CONFIG_KEYS = ("CANVAS_BASE_URL", "CANVAS_API_TOKEN")


class EClassError(Exception):
    """An actionable failure safe to display without response bodies."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Canvas:
    def __init__(self, token):
        self.opener = build_opener(NoRedirect())
        self.headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    def request(self, route, url):
        target = urlsplit(url)
        if (target.scheme, target.netloc, target.path) != ("https", HOST, API + route):
            raise EClassError("Canvas returned a pagination link outside the requested endpoint.")

        request = Request(url, headers=self.headers, method="GET")
        for attempt in range(2):
            try:
                with self.opener.open(request, timeout=12) as response:
                    return json.load(response), response.headers.get("Link", "")
            except HTTPError as error:
                status = error.code
                retry_after = error.headers.get("Retry-After", "1")
                error.close()
                if attempt == 0 and status in (429, 502, 503, 504):
                    if retry_after.isascii() and retry_after.isdecimal() and len(retry_after) <= 2:
                        seconds = int(retry_after)
                        if seconds <= 4:
                            time.sleep(seconds)
                            continue
                if status in (401, 403):
                    detail = "Check token validity and the course's permissions."
                    if route.endswith("/files"):
                        detail = "Course files may be restricted. Open the course in the LMS for its materials."
                elif status == 404:
                    detail = "Check the IDs and whether the item is visible to your account."
                elif status == 429:
                    detail = "Canvas is rate limiting requests. Try again later."
                elif 300 <= status < 400:
                    detail = "Canvas redirected the API request. Check CANVAS_BASE_URL and your token."
                else:
                    detail = "Canvas could not complete the request."
                raise EClassError(f"GET {API}{route} returned HTTP {status}. {detail}") from None
            except (URLError, OSError):
                raise EClassError(
                    f"Could not reach {HOST} for {API}{route}. Check network access from the runner."
                ) from None
            except (ValueError, UnicodeError):
                raise EClassError(f"GET {API}{route} returned invalid JSON.") from None

    def object(self, route, params=None):
        url = f"{ORIGIN}{API}{route}?{urlencode(params or {}, doseq=True)}"
        value, _ = self.request(route, url)
        if not isinstance(value, dict):
            raise EClassError(f"GET {API}{route} returned an unexpected response.")
        return value

    def rows(self, route, params=None):
        query = urlencode({"per_page": 50, **(params or {})}, doseq=True)
        url = f"{ORIGIN}{API}{route}?{query}"
        seen = set()
        rows = []
        for _ in range(MAX_PAGES):
            if url in seen:
                raise EClassError(f"Canvas repeated a pagination link for {API}{route}.")
            seen.add(url)
            page, links = self.request(route, url)
            if not isinstance(page, list) or any(not isinstance(row, dict) for row in page):
                raise EClassError(f"GET {API}{route} returned an unexpected response.")
            rows.extend(page)
            next_page = NEXT_PAGE.search(links)
            if next_page is None:
                return rows
            url = urljoin(url, next_page.group(1))
        raise EClassError(f"GET {API}{route} exceeded {MAX_PAGES} pages. Use a narrower query.")


class CourseText(HTMLParser):
    """Convert Canvas HTML fields to text without loading linked resources."""

    blocks = {"address", "article", "blockquote", "br", "div", "h1", "h2", "h3", "h4",
              "h5", "h6", "li", "ol", "p", "pre", "section", "td", "th", "tr", "ul"}
    ignored = {"script", "style", "template"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self.ignore_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.ignored:
            self.ignore_depth += 1
        if not self.ignore_depth and tag in self.blocks:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.ignored and self.ignore_depth:
            self.ignore_depth -= 1
        if not self.ignore_depth and tag in self.blocks:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.ignore_depth:
            self.parts.append(data)


def plain_text(html):
    parser = CourseText()
    parser.feed(html or "")
    parser.close()
    lines = (" ".join(line.split()) for line in "".join(parser.parts).splitlines())
    return "\n".join(line for line in lines if line)


def excerpt(text, limit=8000):
    return {"text": text[:limit], "truncated": len(text) > limit}


def canvas_link(value, fallback=None):
    if value:
        try:
            target = urlsplit(urljoin(ORIGIN, value))
        except ValueError:
            pass
        else:
            if target.scheme == "https" and target.netloc == HOST:
                return urlunsplit(("https", HOST, target.path, "", ""))
    return ORIGIN + fallback if fallback else None


def kst_time(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not parsed.tzinfo:
        parsed = parsed.replace(tzinfo=KST)
    return parsed.astimezone(KST).isoformat()


def today():
    return datetime.now(KST).date()


def matching_courses(api, term, search=None, scores=False):
    includes = ["term", "total_scores"] if scores else ["term"]
    courses = api.rows("courses", {"enrollment_type": "student", "include[]": includes})
    courses = [row for row in courses if row.get("name") and row.get("id") is not None]
    term_name = term
    if term == "current":
        regular, started = set(), set()
        current_date = today().isoformat()
        for course in courses:
            item = course.get("term") or {}
            name, start = (item.get("name") or "").strip(), kst_time(item.get("start_at"))
            if name and start and start[:10] <= current_date and not DEFAULT_TERM.search(name):
                started.add((start, name))
                if REGULAR_TERM.fullmatch(name):
                    regular.add((start, name))
        # Prefer regular semesters so a short winter or summer session does not hide them.
        candidates = regular or started
        if not candidates:
            raise EClassError("Could not identify the current semester. Try courses --term all.")
        term_name = max(candidates)[1]
        courses = [row for row in courses if (row.get("term") or {}).get("name") == term_name]
    elif term != "all":
        courses = [
            row for row in courses
            if term.casefold() in ((row.get("term") or {}).get("name") or "").casefold()
        ]
    if search:
        courses = [row for row in courses if any(
            search.casefold() in (row.get(key) or "").casefold() for key in ("name", "course_code")
        )]
    return term_name, courses


def course_summary(course):
    course_id = course["id"]
    term = course.get("term") or {}
    return {
        "id": course_id, "name": course.get("name"), "code": course.get("course_code"),
        "term": term.get("name"), "term_start_at": kst_time(term.get("start_at")),
        "term_end_at": kst_time(term.get("end_at")),
        "url": f"{ORIGIN}/courses/{course_id}",
    }


def marks(submission):
    keys = ("submitted_at", "graded_at", "posted_at", "score", "grade", "missing", "late",
            "excused", "workflow_state")
    result = {key: submission.get(key) for key in keys}
    for key in ("submitted_at", "graded_at", "posted_at"):
        result[key] = kst_time(result[key])
    return result


def assignment_summary(course_id, item):
    info = {
        "id": item["id"], "course_id": course_id, "name": item.get("name"),
        "due_at": kst_time(item.get("due_at")), "points_possible": item.get("points_possible"),
        "lock_at": kst_time(item.get("lock_at")), "locked_for_user": item.get("locked_for_user"),
        "submission_types": item.get("submission_types") or [],
        "url": canvas_link(item.get("html_url"), f"/courses/{course_id}/assignments/{item['id']}"),
    }
    if isinstance(item.get("submission"), dict):
        info["submission"] = marks(item["submission"])
    return info


def listing(rows, args, **context):
    items = rows[:args.limit]
    return {**context, "matched": len(rows), "shown": len(items), "items": items}


def course_list(api, args):
    term, courses = matching_courses(api, args.term, args.search)
    rows = sorted(map(course_summary, courses), key=lambda r: (r["name"], r["term"] or ""))
    return listing(rows, args, term=term)


def grades(api, args):
    if args.course:
        route = f"courses/{args.course}"
        courses = [api.object(route, {"include[]": ["term", "total_scores"]})]
        term = None
    else:
        term, courses = matching_courses(api, args.term, scores=True)
    rows = []
    for course in courses:
        enrollment = next((e for e in course.get("enrollments") or [] if e.get("type") == "student"), {})
        score_fields = ("computed_current_score", "computed_final_score",
                        "computed_current_grade", "computed_final_grade")
        row = {**course_summary(course), **{key: enrollment.get(key) for key in score_fields}}
        rows.append(row)
    rows.sort(key=lambda row: row["name"] or "")
    return listing(rows, args, term=term)


def selected_courses(api, args):
    if args.course:
        return None, {str(args.course): None}
    term, courses = matching_courses(api, args.term)
    return term, {str(course["id"]): course.get("name") for course in courses}


def missing(api, args):
    term, courses = selected_courses(api, args)
    items = api.rows("users/self/missing_submissions") if courses else []
    rows = [
        {**assignment_summary(item["course_id"], item), "course": courses[str(item["course_id"])]}
        for item in items if str(item.get("course_id")) in courses
    ]
    rows.sort(key=lambda row: row["due_at"] or "")
    return listing(rows, args, term=term, course_id=args.course)


def assignments(api, args):
    route = f"courses/{args.course_id}/assignments"
    items = api.rows(route, {"include[]": "submission"})
    rows = [
        assignment_summary(args.course_id, item) for item in items
        if not args.search or args.search.casefold() in (item.get("name") or "").casefold()
    ]
    if args.unsubmitted:
        rows = [
            row for row in rows
            if set(row["submission_types"]) - {"none", "not_graded"}
            and (row.get("submission") or {}).get("workflow_state") == "unsubmitted"
            and not row["submission"]["submitted_at"] and not row["submission"]["excused"]
        ]
    rows.sort(key=lambda row: (row["due_at"] is None, row["due_at"] or "", row["name"] or ""))
    return listing(rows, args, course_id=args.course_id)


def assignment(api, args):
    route = f"courses/{args.course_id}/assignments/{args.assignment_id}"
    info = api.object(route, {"include[]": "submission"})
    result = assignment_summary(args.course_id, info)
    result.update({
        "description": excerpt(plain_text(info.get("description"))),
        "unlock_at": kst_time(info.get("unlock_at")),
    })
    try:
        submission = api.object(f"{route}/submissions/self", {"include[]": "submission_comments"})
    except EClassError as error:
        result["feedback_error"] = str(error)
    else:
        result["submission"] = marks(submission)
        comments = submission.get("submission_comments") or []
        result["feedback"] = [
            {"created_at": kst_time(comment.get("created_at")),
             **excerpt(plain_text(comment.get("comment")), limit=2200)}
            for comment in comments[-10:]
        ]
        result["feedback_count"] = len(comments)
    return result


def date_window(args):
    anchor = today()
    if args.start or args.end:
        start = args.start or anchor
        end = args.end or (start + timedelta(days=args.default_days - 1))
    elif args.past:
        start, end = anchor - timedelta(days=(args.days or args.default_days) - 1), anchor
    else:
        start, end = anchor, anchor + timedelta(days=(args.days or args.default_days) - 1)
    if end < start:
        raise EClassError("The end date must be on or after the start date.")
    if (end - start).days >= 366:
        raise EClassError("Use a date window of at most 366 days.")
    return start, end


def timestamp(day):
    return datetime.combine(day, clock_time.min, KST).isoformat()


def within_window(value, start, end):
    return value is not None and start.isoformat() <= value[:10] <= end.isoformat()


def dated_listing(rows, args, term, start, end):
    return listing(rows, args, term=term, course_id=args.course,
                   start=start.isoformat(), end=end.isoformat(), timezone="Asia/Seoul")


def planner(api, args):
    start, end = date_window(args)
    term, courses = selected_courses(api, args)
    params = {"start_date": timestamp(start), "end_date": timestamp(end + timedelta(days=1))}
    if args.course:
        params["context_codes[]"] = f"course_{args.course}"
    items = api.rows("planner/items", params) if courses else []
    rows = []
    for item in items:
        due_at = kst_time(item.get("plannable_date"))
        kind, course_id = item.get("plannable_type"), item.get("course_id")
        if str(course_id) not in courses or not within_window(due_at, start, end):
            continue
        if args.kind and kind != args.kind:
            continue
        flags = item.get("submissions") if isinstance(item.get("submissions"), dict) else {}
        if args.unsubmitted and (kind != "assignment" or flags.get("submitted") is not False
                                 or flags.get("excused") or flags.get("graded")):
            continue
        entry = item.get("plannable") or {}
        entry_id = item.get("plannable_id") or entry.get("id")
        path = f"/courses/{course_id}"
        if entry_id and kind in ("assignment", "announcement"):
            collection = "assignments" if kind == "assignment" else "discussion_topics"
            path += f"/{collection}/{entry_id}"
        rows.append({
            "id": entry_id, "kind": kind, "at": due_at,
            "course_id": course_id, "course": item.get("context_name") or courses[str(course_id)],
            "title": entry.get("title") or entry.get("name"),
            "submitted": flags.get("submitted"), "missing": flags.get("missing"),
            "late": flags.get("late"), "graded": flags.get("graded"),
            "url": canvas_link(item.get("html_url"), path),
        })
    rows.sort(key=lambda row: row["at"])
    return dated_listing(rows, args, term, start, end)


def dated_course_items(api, args):
    start, end = date_window(args)
    term, courses = selected_courses(api, args)
    course_ids = list(courses)
    is_announcement = args.command == "announcements"
    route = "announcements" if is_announcement else "calendar_events"
    params = (
        {"start_date": timestamp(start), "end_date": timestamp(end + timedelta(days=1))}
        if is_announcement else
        {"start_date": start.isoformat(), "end_date": end.isoformat(), "type": "event"}
    )
    items = []
    # Canvas may limit how many calendar contexts a single request includes.
    for offset in range(0, len(course_ids), 10):
        contexts = [f"course_{cid}" for cid in course_ids[offset:offset + 10]]
        items.extend(api.rows(route, {**params, "context_codes[]": contexts}))
    rows = []
    for item in items:
        at = kst_time(item.get("posted_at" if is_announcement else "start_at"))
        title = item.get("title")
        if is_announcement and not within_window(at, start, end):
            continue
        body = plain_text(item.get("message" if is_announcement else "description")) if args.body else ""
        if args.search and args.search.casefold() not in f"{title or ''}\n{body}".casefold():
            continue
        context_code = item.get("context_code") or ""
        course_id = context_code.removeprefix("course_")
        path = f"/courses/{course_id}" if course_id in courses else None
        if path and is_announcement and item.get("id"):
            path += f"/discussion_topics/{item['id']}"
        row = {
            "id": item.get("id"), "title": title, "at": at, "context": context_code,
            "course_id": course_id if course_id in courses else None,
            "course": courses.get(course_id) or item.get("context_name"),
            "url": canvas_link(item.get("html_url"), path),
        }
        if args.body:
            row["body"] = excerpt(body, limit=2500)
        if not is_announcement:
            row["ends_at"] = kst_time(item.get("end_at"))
            row["all_day"] = item.get("all_day")
            row["location"] = item.get("location_name")
        rows.append(row)
    rows.sort(key=lambda row: row["at"] or "", reverse=is_announcement)
    return dated_listing(rows, args, term, start, end)


def announcement(api, args):
    path = f"courses/{args.course_id}/discussion_topics/{args.topic_id}"
    item = api.object(path)
    return {
        "id": item.get("id"), "course_id": args.course_id, "title": item.get("title"),
        "posted_at": kst_time(item.get("posted_at")), "url": canvas_link(item.get("html_url"), f"/{path}"),
        "body": excerpt(plain_text(item.get("message")), limit=16000),
        "attachments": [
            {"name": file.get("display_name") or file.get("filename"), "bytes": file.get("size")}
            for file in item.get("attachments") or [] if isinstance(file, dict)
        ],
    }


def syllabus(api, args):
    course = api.object(f"courses/{args.course_id}", {"include[]": ["term", "syllabus_body"]})
    return {
        "course": course_summary(course),
        "syllabus": excerpt(plain_text(course.get("syllabus_body"))),
        "url": f"{ORIGIN}/courses/{args.course_id}/assignments/syllabus",
    }


def modules(api, args):
    base = f"courses/{args.course_id}/modules"
    if args.module:
        rows = [
            {"id": item.get("id"), "title": item.get("title"), "type": item.get("type"),
             "locked": item.get("locked_for_user"),
             "url": canvas_link(item.get("html_url")),
             "completion_requirement": item.get("completion_requirement")}
            for item in api.rows(f"{base}/{args.module}/items")
        ]
    else:
        rows = [
            {"id": item.get("id"), "name": item.get("name"), "items_count": item.get("items_count"),
             "state": item.get("state"), "unlock_at": kst_time(item.get("unlock_at"))}
            for item in api.rows(base)
        ]
    url = f"{ORIGIN}/{base}" + (f"#module_{args.module}" if args.module else "")
    return listing(rows, args, course_id=args.course_id, module_id=args.module, url=url)


def files(api, args):
    base = f"courses/{args.course_id}/files"
    rows = [
        {"id": item["id"], "name": item.get("display_name"), "bytes": item.get("size"),
         "updated_at": kst_time(item.get("updated_at")), "url": f"{ORIGIN}/{base}/{item['id']}"}
        for item in api.rows(base)
    ]
    return listing(rows, args, course_id=args.course_id)


def check(api, _args):
    profile = api.object("users/self/profile")
    if not profile.get("id"):
        raise EClassError("The profile response did not confirm authentication.")
    return {"authenticated": True, "origin": ORIGIN, "timezone": profile.get("time_zone")}


def positive_int(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("expected a positive integer") from None
    if number < 1:
        raise argparse.ArgumentTypeError("expected a positive integer")
    return number


def max_100(value):
    number = positive_int(value)
    if number > 100:
        raise argparse.ArgumentTypeError("choose a value from 1 to 100")
    return number


def iso_date(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise argparse.ArgumentTypeError("expected a date in YYYY-MM-DD format")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError("expected a valid date in YYYY-MM-DD format") from None


def config_file():
    path = os.environ.get("ECLASS_CONFIG")
    if path:
        return os.path.expanduser(path)
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "eclass", "config")


def load_config():
    """Return settings from the environment, falling back to the config file."""
    values = {}
    path = config_file()
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.removeprefix("export ").split("=", 1)
                key, value = key.strip(), value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                if key in CONFIG_KEYS:
                    values[key] = value
    except FileNotFoundError:
        pass
    except OSError:
        raise EClassError(f"Could not read the config file at {path}.") from None
    for key in CONFIG_KEYS:
        if os.environ.get(key, "").strip():
            values[key] = os.environ[key]
    return {key: values.get(key, "").strip() for key in CONFIG_KEYS}


def base_origin(value):
    """Normalize CANVAS_BASE_URL to an https origin such as https://eclass.example.ac.kr."""
    if "://" not in value:
        value = "https://" + value
    try:
        target = urlsplit(value)
        scheme, host, port = target.scheme, target.hostname, target.port
        has_credentials = target.username is not None or target.password is not None
    except ValueError:
        scheme = host = port = None
        has_credentials = False
    if scheme != "https" or not host or has_credentials:
        raise EClassError("CANVAS_BASE_URL must be an https URL such as https://eclass.example.ac.kr.")
    netloc = host + (f":{port}" if port else "")
    return f"https://{netloc}", netloc


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    def command(name, func, help_text, *, limit=False, course=False, term=False, search=False):
        sub = commands.add_parser(name, help=help_text, description=help_text)
        sub.set_defaults(run=func)
        if limit:
            sub.add_argument("--limit", type=max_100, default=25, help="maximum rows to show (default 25)")
        if course:
            sub.add_argument("--course", type=positive_int, metavar="COURSE_ID")
        if term:
            sub.add_argument("--term", default="current", help="current, all, or part of a term name")
        if search:
            sub.add_argument("--search", help="case-insensitive text to match in the title or name")
        return sub

    def dates(sub, days, past=False):
        sub.set_defaults(default_days=days, past=past)
        sub.add_argument("--days", type=max_100,
                         help=f"relative date window including today (default {days} days)")
        sub.add_argument("--start", type=iso_date, help="first date in KST (YYYY-MM-DD)")
        sub.add_argument("--end", type=iso_date, help="last date in KST, inclusive (YYYY-MM-DD)")

    command("check", check, "Verify token authentication without showing the profile.")
    command("courses", course_list, "List enrolled courses by term.", limit=True, term=True, search=True)
    command("grades", grades, "List available course scores.", limit=True, course=True, term=True)
    command("missing", missing, "List assignments Canvas flags as missing.",
            limit=True, course=True, term=True)
    assignments_parser = command("assignments", assignments, "List assignments and submission status.",
                                 limit=True, search=True)
    assignments_parser.add_argument("course_id", type=positive_int)
    assignments_parser.add_argument("--unsubmitted", action="store_true",
                                    help="show unsubmitted work, including assignments without a deadline")
    assignment_parser = command("assignment", assignment, "Read assignment instructions and own feedback.")
    assignment_parser.add_argument("course_id", type=positive_int)
    assignment_parser.add_argument("assignment_id", type=positive_int)
    planner_parser = command("planner", planner, "List course planner items.", limit=True, course=True, term=True)
    dates(planner_parser, 14)
    planner_parser.add_argument("--kind", help="Canvas item type, e.g. assignment, quiz, or calendar_event")
    planner_parser.add_argument("--unsubmitted", action="store_true",
                                help="show assignments explicitly marked unsubmitted and still outstanding")
    for name, help_text, days, past in (
        ("announcements", "List recent course announcements.", 14, True),
        ("calendar", "List course calendar events.", 14, False),
    ):
        sub = command(name, dated_course_items, help_text, limit=True, course=True, term=True)
        dates(sub, days, past)
        sub.add_argument("--search", help="match the title or, with --body, the title and full plain-text body")
        sub.add_argument("--body", action="store_true", help="include a plain-text excerpt per result")
    announcement_parser = command("announcement", announcement, "Read an individual course announcement.")
    announcement_parser.add_argument("course_id", type=positive_int)
    announcement_parser.add_argument("topic_id", type=positive_int)
    command("syllabus", syllabus, "Read a course's syllabus.").add_argument("course_id", type=positive_int)
    modules_parser = command("modules", modules, "List modules or the items in one module.", limit=True)
    modules_parser.add_argument("course_id", type=positive_int)
    modules_parser.add_argument("--module", type=positive_int, metavar="MODULE_ID")
    command("files", files, "List course file metadata where permitted.", limit=True).add_argument(
        "course_id", type=positive_int)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "days", None) and (args.start or args.end):
        parser.error("use --days or --start/--end")
    if getattr(args, "course", None) and args.term != "current":
        parser.error("use --course or --term")
    if args.command == "planner" and args.unsubmitted and args.kind not in (None, "assignment"):
        parser.error("--unsubmitted applies to assignments")
    global ORIGIN, HOST
    try:
        settings = load_config()
        if not settings["CANVAS_BASE_URL"]:
            raise EClassError(
                f"CANVAS_BASE_URL is not set in the environment or {config_file()}. "
                "Set it to your school's LMS address, e.g. https://eclass.example.ac.kr.")
        ORIGIN, HOST = base_origin(settings["CANVAS_BASE_URL"])
    except EClassError as error:
        print(f"eclass: {error}", file=sys.stderr)
        return 2
    token = settings["CANVAS_API_TOKEN"]
    if not token:
        print(f"eclass: CANVAS_API_TOKEN is not set in the environment or {config_file()}.",
              file=sys.stderr)
        return 2
    if not token.isascii() or any(not 33 <= ord(char) <= 126 for char in token):
        print("eclass: CANVAS_API_TOKEN contains invalid characters.", file=sys.stderr)
        return 2
    try:
        result = args.run(Canvas(token), args)
    except (EClassError, ValueError, OverflowError) as error:
        print(f"eclass: {str(error).replace(token, '[redacted]')}", file=sys.stderr)
        return 1
    output = json.dumps(result, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write((output.replace(token, "[redacted]") + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
