# -*- coding: utf-8 -*-
import django.forms as forms

from django.contrib import admin
from django.shortcuts import render_to_response
from django.template.context import RequestContext

import json

from comicweb.core.models import *
from comicweb.core.indexing import *
import settings

admin.site.register((Issue, Volume, StoryArc, Concept, Publisher, Character, Team, Location))

admin.site.register(( Reading, List, ListEntry, AgeRating ))

logger = logging.getLogger('comicweb.core.admin')


class MaterialAdmin( admin.ModelAdmin ):
    list_display = ['file', 'issue']
    actions = [ 'lookup_issue', 'populate_from_cv' ]

    class LookupIssueForm(forms.Form):
        _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
        _material = forms.ModelChoiceField(Material.objects)

    class PopulateForm(forms.Form):
        _selected_action =  forms.CharField(widget=forms.MultipleHiddenInput)
        _material = forms.ModelChoiceField(Material.objects)


    def populate_from_cv( self, request, queryset ):
        logger.debug('in populate_from_cv. qs:%s' % queryset)
        if 'post' in request.POST:
            logger.debug('in POST')
            cv = ComicVineSearcher()
            _created = []
            for key in request.POST.keys():
                logger.debug('key:%s, value:%s' % (key, request.POST[key]))
                if key.startswith('material_'):
                    _material_id = key[key.find('_')+1:]
                    _material = Material.objects.get(pk=_material_id)
                    bf = BookFile(_material.file)
                    bf.cv_issue_data = cv.get_object_from_cv('http://api.comicvine.com/issue/%s/?api_key=%s&format=json' % (request.POST.get(key) , settings.CV_API_KEY))
                    bf._create_issue()
                    _created.append(bf.issue)
            self.message_user(request, 'created %d issues - %s' % (len(_created), _created))
#            import pdb; pdb.set_trace()
        else:
            logger.debug('showing form with queryset %s' % queryset)
            form = self.PopulateForm(initial={'_selected_action': request.POST.getlist(admin.ACTION_CHECKBOX_NAME)})
            return render_to_response(
                'admin/material_from_cv.html',
                { 'qs' : queryset, 'form' : form },
                context_instance = RequestContext(request),
            )
    populate_from_cv.short_description = 'Create issue with info from comicvine'

    def lookup_issue( self, request, queryset ):
        logger.debug('IN LOOKUP_ISSUE')
        form = None
        if 'post' in request.POST:
            logger.debug('saving the lookedup issues')
            cv_ids = json.loads(request.POST.get('cv_ids'))
            cv = ComicVineSearcher()
            _created = []
            for key in cv_ids.keys():
                logger.debug( cv_ids[key] )
                material = Material.objects.get(pk=cv_ids[key]['material_id'])
                bf = BookFile(file=material.file)
                bf.cv_issue_data=cv.get_object_from_cv('http://api.comicvine.com/issue/%s/?api_key=%s&format=json' % (cv_ids[key]['cv_issue_id'] , settings.CV_API_KEY))
                bf._create_issue()
                _created.append(bf.issue)

#            import pdb; pdb.set_trace()
            self.message_user(request, 'created %d issues  - %s' % (len(_created), _created))
            return

        else:
            logger.debug('looking up %s' % queryset)
            res = [{'volumes' : x.get_potential_volumes(), 'material' : x} for x in queryset]
            form = self.LookupIssueForm(initial={'_selected_action': request.POST.getlist(admin.ACTION_CHECKBOX_NAME)})
            return render_to_response('admin/materialadmin.html', {'res' : res, 'form' : form, 'API_KEY' : settings.CV_API_KEY}, context_instance=RequestContext(request) )

    lookup_issue.short_description = 'Lookup up specified material on comicvine'

admin.site.register( Material, MaterialAdmin )
