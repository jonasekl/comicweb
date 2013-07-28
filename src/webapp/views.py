# -*- coding: utf-8 -*-

# -- std libs
import zipfile,rarfile,traceback,json,logging

# -- django imports
from django.http import HttpResponse,HttpResponseRedirect, Http404
from django.shortcuts import render_to_response
from django.template import Context, RequestContext
from django.conf import settings

# -- project imports
from comicweb.core.models import *

# -- globals
logger = logging.getLogger('comciweb.webapp.views')

def _get_recent_list( user ):
    try:
        ret = []
        volumes = []
        for r in Reading.objects.filter(user=user).order_by('when').reverse():
            if not r.issue.volume in volumes:
                volumes.append(r.issue.volume)
                ret.append({'issue' : r.issue, 'latest_reading' : r.issue.get_latest_reading(user)})
        return ret
    except:
        return None
def recent(request):
    recent_list = _get_recent_list(request.user) # maybe ought be like profile.get_recent_list()
#        recent_list = Reading.objects.filter(user=request.user).order_by('when').reverse()#[:20]
    return render_to_response(
        'issues.html',
        {
            'book_list' : recent_list,
            'current_user' : request.user,
            'list_type' : 'recent_list',
        },
        context_instance = RequestContext(request)
    )



def issue_browser(request, volume_id=None):
    if not volume_id:        
        book_list = Reading.objects.filter(user=request.user).order_by('when').reverse()
    else:
        book_list = [{'issue' : x, 'latest_reading' : x.get_latest_reading(request.user) } for x in Issue.objects.filter(volume=Volume.objects.get(pk=volume_id)).order_by('publish_year', 'publish_month', 'issue_number').reverse()]
    return render_to_response('issues.html', { 'book_list' : book_list, 'current_user' : request.user , 'list_type' : 'issue_browser'} , context_instance = RequestContext( request ))

def reader(request, issue_id, page):
    page = int(page)
    issue = Issue.objects.get(pk=issue_id)
    issue.register_reading(request.user, page) 
#    import pdb; pdb.set_trace()
#    logger.debug('%s' % request )
    material = issue.get_material() if not request.GET.get('material') else Material.objects.get(pk=request.GET.get('material'))
    pagecount = material.get_pagecount()
    return render_to_response(
        'reader.html',
        {
            'issue' : issue,
            'material' : material,
            'page' : page,
            'previous_page' : (page-1) if (page-1) >= -1 else -1,
            'next_page' : (page+1) if (page+1) <= pagecount else -1,
            'previous_issue' : issue.get_previous(), 
            'next_issue' : issue.get_next(),
            'materials' : Material.objects.filter(issue=issue),
        },
        context_instance = RequestContext(request)
    )
   
def browserOLD(request, publisher_id):
    _publisher = Publisher.objects.get(pk=publisher_id)
    _volumes = [x for x in Volume.objects.filter(publisher=_publisher).order_by('name') if len(x.issue_set.all())>0]
    if request.GET.get('ongoing') == 'true':
        _volumes = [x for x in _volumes if x.is_ongoing()]
    _publishers = [x for x in Publisher.objects.all() if len(x.volume_set.all())>0]
    return render_to_response(
        'browser.html',
        {
            'publisher_id' : int(publisher_id),
            'publishers' : _publishers,
            'publisher' : _publisher,
            'volumes' : _volumes,        
        },
        context_instance = RequestContext(request)
    )  

def browser( request ):
    _pubs = Publisher.objects.all()
    return render_to_response(
        'browser.html', {'publishers' : _pubs}, context_instance = RequestContext(request)
    )

def mobile( request ):
    _pubs = Publisher.objects.all()
    return render_to_response(
        'mobile.html', {'publishers' : _pubs}, context_instance = RequestContext(request)
    )
