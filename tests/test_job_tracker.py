"""Unit tests for job_tracker.py — pure functions only (no Gmail API calls)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from job_tracker import (
    is_blocked,
    is_academic_email,
    detect_status_regex,
    extract_company,
    extract_role,
    detect_source,
)


# ── is_blocked ────────────────────────────────────────────────────────────────

class TestIsBlocked:
    def test_uaw_blocked(self):
        assert is_blocked("ACT-UAW <act@uaw.org>", "Union update") is True

    def test_yankees_blocked(self):
        assert is_blocked("New York Yankees <news@yankees.com>", "Game tonight") is True

    def test_kaggle_blocked(self):
        assert is_blocked("Kaggle <no-reply@kaggle.com>", "Your competition results") is True

    def test_normal_recruiter_not_blocked(self):
        assert is_blocked("recruiter@stripe.com", "Your application at Stripe") is False

    def test_glassdoor_jobs_blocked(self):
        assert is_blocked("Glassdoor Jobs <noreply@glassdoor.com>", "New jobs for you") is True

    def test_normal_company_not_blocked(self):
        assert is_blocked("Jane Smith <jane@google.com>", "Interview invitation") is False


# ── is_academic_email ─────────────────────────────────────────────────────────

class TestIsAcademicEmail:
    def test_edu_sender_is_academic(self):
        assert is_academic_email("admin@nyu.edu", "Tuition due", "Your semester bill is ready.") is True

    def test_edu_career_center_not_academic(self):
        assert is_academic_email(
            "careers@nyu.edu",
            "Recruiting event at NYU career fair",
            "Join us for on-campus recruiting.",
        ) is False

    def test_non_edu_with_academic_content(self):
        # 2+ academic hits in subject+body → academic
        assert is_academic_email(
            "admin@school.com",
            "Syllabus for next semester",
            "Please review the course syllabus for lectures and office hours.",
        ) is True

    def test_non_edu_single_hit_not_academic(self):
        assert is_academic_email(
            "hr@company.com",
            "Your application",
            "Thank you for applying to our role.",
        ) is False

    def test_non_edu_job_email_not_academic(self):
        assert is_academic_email(
            "recruiting@meta.com",
            "Software Engineer application received",
            "We have received your application for the Software Engineer position.",
        ) is False


# ── detect_status_regex ───────────────────────────────────────────────────────

class TestDetectStatusRegex:
    def test_offer_detected(self):
        assert detect_status_regex("We are pleased to offer you the position") == "Offer"

    def test_offer_welcome_aboard(self):
        assert detect_status_regex("Welcome aboard! Your start date is May 5th.") == "Offer"

    def test_offer_compensation(self):
        assert detect_status_regex("Please review your compensation package and signing bonus.") == "Offer"

    def test_rejected_not_moving_forward(self):
        assert detect_status_regex("We will not be moving forward with your application.") == "Rejected"

    def test_rejected_regret(self):
        assert detect_status_regex("We regret to inform you that you were not selected.") == "Rejected"

    def test_rejected_other_candidates(self):
        assert detect_status_regex("We've decided to move forward with other candidates.") == "Rejected"

    def test_interview_calendly(self):
        assert detect_status_regex("Please book a time at calendly.com/recruiter/interview") == "Interview"

    def test_interview_zoom(self):
        assert detect_status_regex("Join us at zoom.us/j/123456 for your phone screen.") == "Interview"

    def test_interview_hackerrank(self):
        assert detect_status_regex("Complete your assessment at hackerrank.com/test/abc") == "Interview"

    def test_interview_invitation(self):
        assert detect_status_regex("We'd like to invite you for an interview next week.") == "Interview"

    def test_interview_schedule_link(self):
        assert detect_status_regex("Please select a time slot for a 30-min call with our team.") == "Interview"

    def test_applied_received(self):
        assert detect_status_regex("Your application has been received. Thank you for applying.") == "Applied"

    def test_applied_confirmation(self):
        assert detect_status_regex("Application confirmation: Software Engineer at Acme Corp.") == "Applied"

    def test_noise_job_alert(self):
        assert detect_status_regex("Job alert: 15 new jobs matching your profile") == "Unknown"

    def test_noise_recommended(self):
        assert detect_status_regex("Recommended jobs based on your resume") == "Unknown"

    def test_unknown_generic(self):
        assert detect_status_regex("Hi, we found your profile interesting.") == "Unknown"

    def test_priority_offer_over_applied(self):
        # Email contains both confirmation language and offer language → Offer wins
        text = "Thank you for applying. We are pleased to offer you the position."
        assert detect_status_regex(text) == "Offer"

    def test_priority_rejected_over_applied(self):
        text = "Thank you for applying. Unfortunately we will not be moving forward."
        assert detect_status_regex(text) == "Rejected"


# ── extract_company ───────────────────────────────────────────────────────────

class TestExtractCompany:
    def test_display_name(self):
        assert extract_company("Stripe Recruiting <recruiting@stripe.com>") == "Stripe Recruiting"

    def test_skip_generic_display_name(self):
        # "noreply" display name → fall back to domain
        result = extract_company("noreply <noreply@stripe.com>")
        assert result == "Stripe"

    def test_domain_fallback(self):
        result = extract_company("jobs@airbnb.com")
        assert result == "Airbnb"

    def test_skip_gmail_domain(self):
        result = extract_company("someone@gmail.com")
        assert result == "Unknown"

    def test_quoted_display_name(self):
        result = extract_company('"Google Careers" <careers@google.com>')
        assert result == "Google Careers"


# ── extract_role ──────────────────────────────────────────────────────────────

class TestExtractRole:
    def test_role_position_keyword(self):
        # Pattern 3: "[role] position" in body
        role = extract_role(
            "Thank you for applying",
            "We received your application for the Software Engineer position.",
        )
        assert "Software Engineer" in role

    def test_role_applied_for(self):
        # Pattern 2: "applied for the [role] role" — no trailing "at Company" to avoid Pattern 1 grabbing "at X"
        role = extract_role(
            "Application received",
            "You applied for the Data Scientist role.",
        )
        assert "Data Scientist" in role

    def test_unknown_when_no_role(self):
        role = extract_role("Interview invitation", "We'd like to meet with you.")
        assert role == "Unknown"


# ── detect_source ─────────────────────────────────────────────────────────────

class TestDetectSource:
    def test_linkedin(self):
        assert detect_source("jobs-noreply@linkedin.com") == "LinkedIn"

    def test_greenhouse(self):
        assert detect_source("no-reply@greenhouse.io") == "Greenhouse"

    def test_lever(self):
        assert detect_source("no-reply@hire.lever.co") == "Lever"

    def test_workday(self):
        assert detect_source("recruiting@myworkday.com") == "Workday"

    def test_indeed(self):
        assert detect_source("noreply@indeed.com") == "Indeed"

    def test_direct(self):
        assert detect_source("recruiter@stripe.com") == "Direct"
