# -*- coding: utf-8 -*-
# --- std lib imports
import urllib2,urllib,traceback
# --- django imports
from django.http import HttpResponse,HttpResponseRedirect, Http404
from django.conf import settings
from django.forms import model_to_dict
from django.core.serializers.json import DjangoJSONEncoder
# --- project imports
from comicweb.core.models import *

logger = logging.getLogger('comicweb.resourceapp.views')
def thumbnail(request, issue_id):
#    logger.debug('thumbnail->issue_id:%s' % str(issue_id))
    try:
        issue = Issue.objects.get(pk=issue_id)
        _img_path = '%s/issues/%s.jpg' % (settings.THUMBNAIL_PATH, issue.cvid)
        if not os.path.exists(_img_path):
             _get_image_from_cv( issue.cvid, _img_path )
        return HttpResponse(open(_img_path, 'rb').read(), content_type='image/jpeg')
    except:
#        logger.warn('The requested issue does not exist (issue_id=%s)' % str(issue_id))
        logger.warn('Unable to get thumbnail for the requested issue (id #s):\n' % (str(issue_id), traceback.format_exc()))
        return HttpResponse('The requested issue does not exist', status=404)

def _get_image_from_cv(cv_issue_id, img_path):
    try:
        _url = 'http://api.comicvine.com/issue/%s/?api_key=%s&format=json' % (cv_issue_id, settings.CV_API_KEY)
        _issue_obj = json.loads(urllib2.urlopen(_url).read())
        _thumbnail_path = _issue_obj['results']['image']['thumb_url']
        urllib.urlretrieve(_thumbnail_path, filename=img_path)
    except:
        traceback.print_exc()


def page(request, material_id, page):
    try:
        material = Material.objects.get(pk=material_id)
        resp = HttpResponse( material.get_page(page), content_type="image/jpeg" )
        resp['material_id'] = material.id
        resp['original_filename'] = material.file.encode('utf-8')
        resp['filename'] = material.get_filename()
        if material.issue:
            resp['issue_id'] = material.issue.id
        return resp
    except:
        logger.error('error getting page (material_id:%s, page:%s):\n%s' % (material_id, str(page), traceback.format_exc()))
        return HttpResponse('<pre>%s</pre>' % traceback.format_exc(), status=500)

def download_issue(request, issue_id):
    '''
    Outputs material for an issue in pure binary format.
    '''
    try:
        issue = Issue.objects.get(pk=issue_id)
        material = issue.get_material()
        content_type = 'application/zip' if 'cbz' in material.file.lower() else 'application/rar'
        resp = HttpResponse(open(material.file, 'rb').read(), content_type=content_type)
        resp['Content-Disposition'] = 'attachment; filename=%s' % material.get_filename()
        return resp
    except Issue.DoesNotExist:
        return Http404('Issue does not exist')
    except Material.DoesNotExist:
        return Http404('Material for requested issue does not exist')
    except:
        return HttpResponse('Unable to download issue', status=500)

def download_material( request, material_id):
    try:
        material = Material.objects.get(pk=material_id)
        content_type = 'application/zip' if 'cbz' in material.file.lower() else 'application/rar'
        resp = HttpResponse(open(material.file, 'rb').read(), content_type=content_type)
        resp['Content-Disposition'] = 'attachment; filename=%s' % material.get_filename()
        return resp
    except:
        return Http500('')

def auto_suggest( request, search_term ):
    try:
        hits =  []
        for hit in Volume.objects.filter( name__istartswith=search_term ).order_by('start_year').reverse():
            hits.append({'value' : hit.name, 'name' : hit.name, 'id' : hit.id})
        return HttpResponse(json.dumps( hits ), content_type='application/json')
    except:
        logger.warn('exception in auto_suggest:\n %s' % traceback.format_exc())
        return HttpResponse(json.dumps([]), content_type='application/json')

def issues( request, volume_id ):
#    import pdb; pdb.set_trace()
    try:
        _issues = Issue.objects.filter(volume=Volume.objects.get(pk=volume_id)).order_by('issue_number').reverse()
        _cur_user = request.META.get('HTTP_X_COMICWEB_USER')
        logger.debug('current user:%s' % _cur_user)
        if _cur_user is not None:
            _readings = [x.get_latest_reading(User.objects.get(username=_cur_user)) for x in _issues]
        _issues_as_dicts = [{'issue' : model_to_dict(x), 'reading' : x.get_latest_reading(User.objects.get(username=_cur_user))} for x in _issues] if _cur_user is not None else [{'issue' : model_to_dict(x), } for x in _issues]
        for _issue in _issues_as_dicts:
             logger.debug(_issue)
             if _issue.get('reading', None) is not None:
                _issue['reading'] = model_to_dict(_issue['reading'])
                _issue['reading']['when'] = _issue['reading']['when'].isoformat()
#        import pdb; pdb.set_trace()

#        _ret = {'issues' : _issues_as_dicts, 'readings' : _readings_as_dicts}
        return HttpResponse(simplejson.dumps(_issues_as_dicts), content_type='application/json')
    except:
        logger.warn('unable to get issues for json resource:\n%s' % traceback.format_exc())
        return HttpResponse('unable to get issues for json resource for volume %s' % volume_id, status=404)

def publishers_vanilla( request ):
    logger.debug("publishers... %s" % request.GET)
    _cur_user = request.META.get('HTTP_X_COMICWEB_USER')
    kwargs = {}
    if request.GET.get("pk"):
        kwargs["pk"] = int(request.GET.get("pk"))
    if request.GET.get("name"):
        kwargs["name__icontains"] = request.GET.get("name")
    pubs = Publisher.objects.filter(**kwargs)

    return HttpResponse(simplejson.dumps([model_to_dict(x) for x in pubs]), content_type='application/json')

def publishers( request ):
    _cur_user = request.META.get('HTTP_X_COMICWEB_USER')
    kwargs = {}
    if request.GET.get("pk"):
        kwargs["pk"] = int(request.GET.get("pk"))
    if request.GET.get("name"):
        kwargs["name__icontains"] = request.GET.get("name")
    pubs = Publisher.objects.filter(**kwargs)
    pubs_with_sum = []
    for p in pubs:
        pubs_with_sum.append({'publisher' : p, 'sum' : sum([len(x.issue_set.all()) for x in p.volume_set.all()])});
    pubs_with_sum = sorted(pubs_with_sum, key=lambda k: k['sum'], reverse=True)

    return HttpResponse(simplejson.dumps([model_to_dict(x['publisher']) for x in pubs_with_sum]), content_type='application/json')

def volumes( request ):
    """ This is a generic filtering method for volumes
    """
    _cur_user = request.META.get('HTTP_X_COMICWEB_USER')
    if _cur_user:
        logger.debug('_cur_user : %s' % _cur_user)
    kwargs = {}
    if request.GET.get('publisher_id'):
        kwargs[ 'publisher_id'  ] = request.GET.get('publisher_id')
    if request.GET.get('start_year'):
        kwargs[ 'start_year'  ] = request.GET.get('start_year')
    if request.GET.get('name'):
        kwargs['name__icontains'] = request.GET.get('name')
    if request.GET.get('pk'):
        kwargs['pk'] = request.GET.get('pk')
    offset = 0 if not request.GET.get('offset') else int(request.GET.get('offset'))
    limit = 50 if not request.GET.get('limit') else int(request.GET.get('limit'))

    vols = Volume.objects.filter(**kwargs)[offset:offset+limit]
    # special case for is_ongoing, which is not a db field
    if request.GET.get('is_ongoing'):
        vols =  [x for x in vols if x.is_ongoing()]

    # special case for min_issues -
    if request.GET.get('min_issues'):
        vols = [ x for x in vols if len(x.issue_set.all()) > int(request.GET.get('min_issues')) ]

    vols_as_dicts = [] # [model_to_dict(x) for x in vols]
    for v in vols:
        try:
            _vol_as_dict = model_to_dict(v)
            _vol_as_dict['latest_issue'] = model_to_dict(v.get_latest_issue())
            vols_as_dicts.append(_vol_as_dict)
        except:
            logger.warn(traceback.format_exc())
    logger.debug('returning %d volumes' % len(vols))
    return HttpResponse(simplejson.dumps(vols_as_dicts), content_type='application/json')


def recent( request ):
    _cur_user = request.META.get('HTTP_X_COMICWEB_USER')
    logger.debug('get recentlist for user %s' % _cur_user)
    ret = []
    volumes = []
    try:
        user = User.objects.get(username=_cur_user)
        for r in Reading.objects.filter(user=user).order_by('when').reverse():
            if not r.issue.volume in volumes:
                volumes.append(r.issue.volume)
                ret.append({'issue' : model_to_dict(r.issue), 'volume' : model_to_dict(r.issue.volume), 'latest_reading' : model_to_dict(r.issue.get_latest_reading(user))})
    except:
        logger.warn("Unable to get recent list :\n%s" % traceback.format_exc())
    return HttpResponse(json.dumps(ret, cls=DjangoJSONEncoder), content_type="application/json")

def userlists( request ):
    logger.debug('userlists')
    try:
        _cur_user = request.META.get('HTTP_X_COMICWEB_USER')
#        _lists = json.dumps(List.objects.filter(user=User.objects.get(username=_cur_user)), cls=DjangoJSONEncoder)
        _lists = [{'name' : x.name, 'id': x.id, 'issues' : [model_to_dict( y ) for y in x.listentry_set.all()] } for x in List.objects.filter(user=User.objects.get(username=_cur_user))]
        logger.debug('_lists: %s' % _lists)
        return HttpResponse(simplejson.dumps(_lists), content_type='application/json')
    except:
        logger.error(traceback.format_exc())
        return HttpResponse(traceback.format_exc(), status=500)
