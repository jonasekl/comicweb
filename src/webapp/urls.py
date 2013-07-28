from django.conf.urls.defaults import patterns, include, url

from comicweb.webapp.views import *

urlpatterns = patterns('',
    url(r'^recent', 'comicweb.webapp.views.recent'),
    url(r'^reader/(?P<issue_id>\d+)/(?P<page>\d+)/$', 'comicweb.webapp.views.reader'),
    url(r'^issues/(?P<volume_id>\d+)/$', 'comicweb.webapp.views.issue_browser'),
#    url(r'^browser/(?P<publisher_id>\d+)/$', 'comicweb.webapp.views.browser'),
    url(r'^browser/$', 'comicweb.webapp.views.browser'),
    url(r'^mobile/$', 'comicweb.webapp.views.mobile'),
)
