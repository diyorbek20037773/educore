"""Public website URLs (SPEC §6). Mounted inside `i18n_patterns` (uz has no prefix)."""

from __future__ import annotations

from django.urls import path

from apps.web.views import (
    analytics,
    appeals,
    education,
    events,
    feeds,
    home,
    institutions,
    news,
    pages,
    professions,
    search,
    stories,
)

app_name = "web"

urlpatterns = [
    path("", home.home, name="home"),
    path("partials/jonli-lenta/", home.live_panel, name="live_panel"),
    # Institutions
    path("muassasalar/", institutions.institution_list, name="institution_list"),
    path("muassasalar/taqqoslash/", institutions.compare, name="institution_compare"),
    path("muassasalar/taqqoslash/csv/", institutions.compare_csv, name="institution_compare_csv"),
    path("muassasalar/<slug:slug>/", institutions.overview, name="institution_detail"),
    path("muassasalar/<slug:slug>/yonalishlar/", institutions.programs, name="institution_programs"),
    path("muassasalar/<slug:slug>/qabul/", institutions.admissions, name="institution_admissions"),
    path("muassasalar/<slug:slug>/hayot/", institutions.life, name="institution_life"),
    path("muassasalar/<slug:slug>/yangiliklar/", institutions.news, name="institution_news"),
    path("muassasalar/<slug:slug>/tadbirlar/", institutions.events, name="institution_events"),
    path("muassasalar/<slug:slug>/aloqa/", institutions.contacts, name="institution_contacts"),
    # News and long-reads
    path("yangiliklar/", news.news_list, name="news_list"),
    path("yangiliklar/<slug:slug>/", news.news_detail, name="news_detail"),
    path("maqolalar/", news.longread_list, name="longread_list"),
    path("maqolalar/<slug:slug>/", news.longread_detail, name="longread_detail"),
    # Education
    path("yonalishlar/", education.program_list, name="program_list"),
    path("yonalishlar/<slug:institution>/<slug:slug>/", education.program_detail, name="program_detail"),
    path("qabul/", education.admissions, name="admissions"),
    path("talabalar/", education.students_hub, name="students_hub"),
    path("kursantlar/", education.cadets_hub, name="cadets_hub"),
    # Professions, events, motivation
    path("kasblar/", professions.profession_list, name="profession_list"),
    path("kasblar/<slug:slug>/", professions.profession_detail, name="profession_detail"),
    path("tadbirlar/", events.event_list, name="event_list"),
    path("tadbirlar/<slug:slug>/", events.event_detail, name="event_detail"),
    path("tadbirlar/<slug:slug>/ics/", events.event_ics, name="event_ics"),
    path("motivatsiya/", stories.story_list, name="story_list"),
    path("motivatsiya/<slug:slug>/", stories.story_detail, name="story_detail"),
    # Analytics
    path("analitika/", analytics.analytics, name="analytics"),
    path("analitika/data/<slug:chart>/", analytics.chart_data, name="analytics_data"),
    # Appeals (backend in Phase 6)
    path("murojaat/", appeals.appeal_form, name="appeal_form"),
    path("murojaat/yuborildi/<str:code>/", appeals.appeal_success, name="appeal_success"),
    path("murojaat/kuzatish/", appeals.appeal_track, name="appeal_track"),
    # Search
    path("qidiruv/", search.search, name="search"),
    path("qidiruv/takliflar/", search.suggest, name="search_suggest"),
    # Feeds
    path("rss/", feeds.LatestArticlesFeed(), name="rss"),
    path("rss/kategoriya/<slug:slug>/", feeds.CategoryFeed(), name="rss_category"),
    path("rss/<slug:slug>/", feeds.InstitutionFeed(), name="rss_institution"),
    # Static pages
    path("biz-haqimizda/", pages.page, {"slug": "biz-haqimizda"}, name="about"),
    path("aloqa/", pages.page, {"slug": "aloqa"}, name="contact"),
    path("maxfiylik-siyosati/", pages.page, {"slug": "maxfiylik-siyosati"}, name="privacy"),
    path("foydalanish-shartlari/", pages.page, {"slug": "foydalanish-shartlari"}, name="terms"),
]
