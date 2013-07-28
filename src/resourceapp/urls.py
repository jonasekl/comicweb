from django.conf.urls.defaults import patterns, include, url

from comicweb.resourceapp.views import *

urlpatterns = patterns('',
    # -- JSON resources
    url(r'^json/autosuggest/(?P<search_term>.*)/$', 'comicweb.resourceapp.views.auto_suggest'),
    url(r'^json/issues/(?P<volume_id>\d+)/$', 'comicweb.resourceapp.views.issues'),
    url(r'^json/volumes/$', 'comicweb.resourceapp.views.volumes'),
    url(r'^json/publishers/$', 'comicweb.resourceapp.views.publishers'),
    url(r'^json/userlists/$', 'comicweb.resourceapp.views.userlists'),
    url(r'^json/recent/$', 'comicweb.resourceapp.views.recent'),

    # -- BINARY resources
    url(r'^binary/thumbnail/(?P<issue_id>\d+)/$', 'comicweb.resourceapp.views.thumbnail'),
    url(r'^binary/page/(?P<material_id>\d+)/(?P<page>\d+)/$', 'comicweb.resourceapp.views.page'),
)

