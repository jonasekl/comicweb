#-*- coding: latin-1*-
# --- std lib imports
import json,urllib2,requests,urllib,os,traceback,logging
from time import sleep

# --- django imports
from django.conf import settings

# --- project imports
from comicweb.core.models import *

# -- globals
logger = logging.getLogger('comicweb.core.indexing')

class BookFile:
    def __init__(self, file, sleep_time=2):
        self.cv = ComicVineSearcher()
        self.file = file
        self.cv_volume_id = None
        self.issue = -1
        self.title = None
        self.links = []
        self._parse_title()
        self.sleep_time = sleep_time

    def __repr__(self):
        return '%s %d' % (self.title, self.issue)

    def _parse_title(self):
        f = self.file[self.file.rfind('/')+1:]
        if '(' in f:
            _f = f[0:f.find('(')]
            try:
                self.issue = float( _f.strip().split(" ")[-1] )
                self.title = " ".join(_f.strip().split(" ")[0:-1])
            except:
                logger.debug( "%s does not end in a number" % _f )
                self.title = _f
        else:
            self.title = f
        logger.debug('title parsed as %s' % self.title)

    def get_potential_volumes(self):
        from comicweb.core.models import Issue,Material
        self.cv = ComicVineSearcher()
        logger.debug('getting potential volume matches for %s' % self )
        self.links = self._get_google_links()
        _volume_ids=self.get_potential_volumes_from_db()
        _volumes = []
        for link in self.links:
            _volume_id = link[link.rfind('-')+1:len(link)-1]
            if _volume_id in _volume_ids:
                logger.debug('volume_id %s was already in list (might have come from local db search), so will not add again' % _volume_id)
                continue
            if not '?' in _volume_id and not '/' in _volume_id:
                try:
                    _volume_ids.append(int(_volume_id))
                except:
                    pass
        _volume_ids.sort(reverse=True)
        for _id in list(set(_volume_ids)): 
            _volumes.append( self.cv.get_object_from_cv( 'http://api.comicvine.com/volume/%s/?api_key=%s&format=json' % (_id, self.cv.api_key) ) )

        logger.debug('potential volumes for %s : %s' % (self, _volume_ids))
#        import pdb; pdb.set_trace()
        return _volumes

    def get_potential_volumes_from_db(self):
        from comicweb.core.models import *
        logger.debug('get volumes from db for %s' % self.title)
        _vols = Volume.objects.filter(name__contains=self.title)
        logger.debug('db vols:%s' % _vols)
        return [x.cvid for x in _vols]

    def get_potential_issues(self):
        logger.debug('get_potential_issues')
        _volumes = self.get_potential_volumes()
        _potential_issues = []
        for _vol in _volumes:
            for _iss in _vol.get('issues'):
#                import pdb; pdb.set_trace()
                if _iss.get('issue_number') == self.issue:
                    _iss['cv_data'] = self.cv.get_object_from_cv('http://api.comicvine.com/issue/%s/?api_key=%s&format=json' % (_iss.get('id'), self.cv.api_key) )
                _potential_issues.append(_iss)
        return _potential_issues

    #TODO: Make sure there is no Issue for this Material already!
    def lookup(self):
        from comicweb.core.models import Issue # wth???
        logger.debug('looking up %s' % self)
        self.links = self._get_google_links()
        self.cv_issue_data = self._get_issue_data()
        if self.cv_issue_data is None:
            logger.warn('was unable to retrieve comicvine data for %s' % self)
            return
        try:
            # if the issue already exists, update it.
            #_issue_list = [x for x in Issue.objects.all() if self.file in [y.file for y in x.material_set.all()]]
            _issue = Issue.objects.get(cvid=self.cv_issue_data.get('id'))
            _material_files = [x.file for x in _issue.material_set.all()]
            if self.file in _material_files:
                logger.debug('this appears to be an issue for this material: %s ' %( _issue))
            else:
                logger.warn('there appears to be an issue(%s) that matches this material, but there is no link' % _issue)
        except Issue.DoesNotExist:
            # if not, create it
            logger.debug('there does not appear to be an issue for this material, so i will create one')
            self._create_issue()
        except:
            logger.error('error when looking up %s:%s' % (self, traceback.format_exc()))

    def _create_issue(self):
        from comicweb.core.models import Issue # wth???
        from comicweb.core.models import Material # wth???
        _volume_obj = self._get_or_add_volume( self.cv_issue_data.get('volume') )
        logger.debug('volume:%s' % _volume_obj)
        _material = Material.objects.get(file=self.file)
        try:
            _iss = Issue.objects.get(cvid=self.cv_issue_data.get('id'))
            logger.warn('An Issue for cvid %s already exists, will not create a duplicate.' % _iss.cvid)
            self.issue = _iss
            _material.issue = _iss
            _material.save()
            logger.debug('Updated material with the already existing issue %s' % _iss)
            return
        except:
            logger.debug('An Issue with this cvid was not found, which is to be excpected.')
            pass
        _story_objs = self._get_or_add_story_arcs(self.cv_issue_data.get('story_arc_credits'))
        logger.debug('storys:%s' % _story_objs)
        _char_objs = self._get_or_add_characters(self.cv_issue_data.get('character_credits'))
        logger.debug('characters:%s' % _char_objs)
        _loc_objs = self._get_or_add_locations(self.cv_issue_data.get('location_credits'))
        logger.debug('locations:%s' % _loc_objs)
        _team_objs = self._get_or_add_teams(self.cv_issue_data.get('team_credits'))
        logger.debug('teams:%s' % _team_objs)
#        import pdb; pdb.set_trace()
        _issue_obj = Issue(volume=_volume_obj, cvid=self.cv_issue_data.get('id'), issue_number=self.cv_issue_data.get('issue_number'), publish_month=self.cv_issue_data.get('publish_month'), publish_year=self.cv_issue_data.get('publish_year'), age_rating=_volume_obj.age_rating)
            
#        _issue_obj.save(cvid=self.cv_issue_data.get('id'), cv_api_detail_url=self.cv_issue_data.get('api_detail_url'))
        _issue_obj.save()
        _material.issue = _issue_obj
        _material.save()
        self.issue = _issue_obj

    def _get_or_add_volume( self, volume_dict ):
        from comicweb.core.models import Volume # wth???
        if volume_dict and volume_dict.get('id'):
            try:
                vObj = Volume.objects.get(cvid=volume_dict.get('id'))
            except: #NotFoundException
                #cv_vol_dict = _get_from_cv('http://api.comicvine.com/volume/%s/?api_key=%s&format=json' % (volume_dict.get('id'), API_KEY) )
                cv_vol_dict = self.cv.get_object_from_cv( 'http://api.comicvine.com/volume/%s/?api_key=%s&format=json' % (volume_dict.get('id'), self.cv.api_key)  )
                if not cv_vol_dict:
                    logger.warn('was unable to fetch volume data from comicvine for volume_id %s' % volume_dict.get('id'))
                    return None
                pub_obj = self._get_or_add_publisher(cv_vol_dict.get('publisher'))
                concept_objs= self._get_or_add_concepts(cv_vol_dict.get('concept_credits'))
                vObj = Volume(cvid=volume_dict.get('id'), cv_api_detail_url=volume_dict.get('api_detail_url'), name=volume_dict.get('name'), publisher=pub_obj, start_year=cv_vol_dict.get('start_year'), description=cv_vol_dict.get('description'), )
#            _get_from_cv('http://api.comicvine.com/volume/%s/api_key=%s&format=json' % (volume_dict.get('cvid'), API_KEY))
                vObj.save()
                logger.info('Added %s to db' % vObj)
            return vObj
        else:
            return None

    def _get_or_add_teams( self,team_dicts ):
        from comicweb.core.models import Team # wth???
        team_objs=[]
        for team_dict in team_dicts:
            try:
                team_obj = Team.objects.get(cvid=team_dict.get('id'))
                team_objs.append(team_obj)
            except: # NotFoundException
                cv_team_dict = self.cv.get_object_from_cv('http://api.comicvine.com/team/%s/?api_key=%s&format=json' % (team_dict.get('id'), self.cv.api_key) )
                if not cv_team_dict:
                    logger.warn( 'was unable to get team data from cv' )
                    continue
#            print '[debug] cv_team_dict:%s' % cv_team_dict
                publisher_obj = self._get_or_add_publisher(cv_team_dict.get('publisher'))
                team_obj = Team(cvid=team_dict.get('id'), cv_api_detail_url=team_dict.get('api_detail_url'), name=team_dict.get('name'), publisher=publisher_obj)
                team_obj.save()
                logger.info( 'added %s to db' % team_obj )
                team_objs.append(team_obj)
        return team_objs


    def _get_or_add_story_arcs( self,story_dicts ):
        from comicweb.core.models import StoryArc # wth???
        story_objs=[]
        if story_dicts is None or not story_dicts:
            return []
        for story_dict in story_dicts:
            try:
                story_obj = StoryArc.objects.get(cvid=story_dict.get('id'))
                story_objs.append(story_obj)
            except: # NotFoundException
                story_obj = StoryArc(cvid=story_dict.get('id'), cv_api_detail_url=story_dict.get('api_detail_url'), name=story_dict.get('name'))
                story_obj.save()
                logger.info( 'added %s to db' % story_obj )
                story_objs.append(story_obj)
        return story_objs

    def _get_or_add_characters( self,character_dicts ):
        from comicweb.core.models import Character # wth???
        character_objs=[]
        for character_dict in character_dicts:
            try:
                character_obj = Character.objects.get(cvid=character_dict.get('id'))
                character_objs.append(character_obj)
            except: # NotFoundException
                character_obj = Character(cvid=character_dict.get('id'), cv_api_detail_url=character_dict.get('api_detail_url'), name=character_dict.get('name'))
                character_obj.save()
                logger.info('added %s to db'%character_obj)
                character_objs.append(character_obj)
        return character_objs

    def _get_or_add_locations( self,location_dicts ):
        from comicweb.core.models import Location # wth???
        location_objs=[]
        for location_dict in location_dicts:
            try:
                location_obj = Location.objects.get(cvid=location_dict.get('id'))
                location_objs.append(location_obj)
            except: # NotFoundException
                location_obj = Location(cvid=location_dict.get('id'), cv_api_detail_url=location_dict.get('api_detail_url'), name=location_dict.get('name'))
                location_obj.save()
                logger.info('added %s to db' % location_obj)
                location_objs.append(location_obj)
        return location_objs

    def _get_or_add_concepts( self,concept_dicts ):
        from comicweb.core.models import Concept # wth???
        concept_objs=[]
        for concept_dict in concept_dicts:
            try:
                concept_obj = Concept.objects.get(cvid=concept_dict.get('id'))
                concept_objs.append(concept_obj)
            except: # NotFoundException
                concept_obj = Concept(cvid=concept_dict.get('id'), cv_api_detail_url=concept_dict.get('api_detail_url'), name=concept_dict.get('name'))
                concept_obj.save()
                logger.info( 'added %s to db' % concept_obj )
                concept_objs.append(concept_obj)
        return concept_objs

    def _get_or_add_publisher( self, pub_dict ):
        from comicweb.core.models import Publisher # wth???
        pub_obj = None
        if pub_dict and pub_dict.get('id'):
            try:
                pub_obj = Publisher.objects.get(cvid=pub_dict.get('id'))
            except:
                logger.debug(traceback.format_exc())
                pub_obj = Publisher(cvid=pub_dict.get('id'), cv_api_detail_url=pub_dict.get('api_detail_url'), name=pub_dict.get('name'))
                pub_obj.save()
                logger.info( 'added %s to db' % pub_obj)
        return pub_obj


    def _get_issue_data(self):
        self.cv = ComicVineSearcher()
        _volume_ids = []
        for link in self.links:
            _volume_id = link[link.rfind('-')+1:len(link)-1]
            if not '?' in _volume_id:
                _volume_ids.append(_volume_id)
        if not _volume_ids:
            logger.warn('did not find a volume_id to query cv for (%r)' % self)
            return None
        _volume_ids.sort()
        _volume_ids.reverse()
        for _volume_id in _volume_ids:
            _issue_data = self._find_issue( _volume_id )
            if _issue_data:
                return _issue_data
            else:
                logger.debug('book %r was not found in volume %s' % (self, _volume_id))
                continue

        logger.warn('found no match for %r' % self)
        return None

    def _find_issue(self, volume_id):
        _issues = self.cv.get_volume_issues( volume_id )
        for _issue in _issues:
            if float(_issue.get('issue_number')) == float(self.issue):
                logger.info('found match for %s' % _issue)
                #_issue_data = self.cv.get_issue_data('%s?api_key=%s&format=json' % (_issue.get('api_detail_url'), self.cv.api_key))
                _issue_data = self.cv.get_issue_data(_issue.get('id'))
                return _issue_data

        logger.debug('found no match for %r in volume_id %s' %(self, volume_id) )
        return None

    def _get_google_links(self):
        try:
            _google = GoogleSearcher(self.title)
            return _google.get_book_links()
        except:
            traceback.print_exc()
            return []

class ComicVineSearcher:
    def __init__( self ):
        self.api_key = settings.CV_API_KEY

    def get_object_from_cv(self, url):
        """docstring for get_object_from_cv"""
        if not 'api_key' in url:
            url = '%s?api_key=%s&format=json' % (url, self.api_key)
        try:
            res = requests.get(url)
            if res.ok:
                return (json.loads(res.content)).get('results')
            else:
                logger.warn('result not ok for url %s.\n%s\n%s' % (url, res.status_code, res.text))
                return None
        except:
            logger.warn('unable to get_object_from_cv\n%s' % traceback.format_exc())
            return None

    def _query_cv(self, url):
        try:
            res = requests.get(url)
            if res.ok:
                return (json.loads(res.content)).get('results')
            else:
                logger.warn('result not ok for url %s.\n%s\n%s' % (url, res.status_code, res.text))
                return None
        except:
            logger.warn('error querying comicvine for url %s\n%s' % (url, traceback.format_exc()))

    def get_volume_issues(self, volume_id):
        logger.debug('searcing comicvine for volume %s ' % (volume_id))
        return (self._query_cv('http://api.comicvine.com/volume/%s/?api_key=%s&format=json'%(volume_id, self.api_key))).get('issues')

    def get_issue_data(self, issue_id):
        logger.debug('searching comicvine for issue %s' % (issue_id))
        return self._query_cv('http://api.comicvine.com/issue/%s/?api_key=%s&format=json'%(issue_id, self.api_key))

class GoogleSearcher:
    ''' searches google using a custom search for comicvine searches '''
    def __init__(self, query):
        self.api_key = settings.GOOGLE_API_KEY
        self.custom_id = settings.GOOGLE_CUSTOM_ID
        self.query = urllib.quote_plus( query )

    def get_book_links(self):
        res = requests.get('https://www.googleapis.com/customsearch/v1?key=%s&cx=%s&q=%s'%(self.api_key, self.custom_id, self.query))
        if res.ok:
            try:
                return [x.get('link', '') for x in (json.loads(res.content)).get('items', None ) if 'comic book)' in x.get('title', '') ]
            except:
                traceback.print_exc()
                logger.warn('content was %s' % res.content)
                return []
        else:
            logger.warn('google was result was not ok\n%s\n%s' % (res.status_code, res.text) )
            return []


def is_comic_file( filepath ):
    try:
        return filepath[filepath.rfind('.')+1:].lower() in ('cbz', 'cbr')
    except:
        return False

class DirectoryIndexer:
    ''' indexes a directory '''
    def __init__(self, path):
        self.path = path

    def parse(self, selpath):
        logger.debug('parsing %s' % selpath)
        for entry in os.listdir( selpath ):
            _path = os.path.join(selpath, entry) 
            if os.path.isdir( _path ):
                self.parse(_path)
            if os.path.isfile( _path ) and is_comic_file(_path):
                try:
                    Material.objects.get(file=_path)
                    logger.warn('Material for %s already exists, skipping' % _path)
                except:
                    _material = Material(file=_path)
                    _material.save()
                    logger.info('%s saved' % _material)

if __name__=='__main__':
    # Usage example from /home/jonas/src/comicweb/comicweb-django/src/comicweb:
    # PYTHONPATH=.. DJANGO_SETTINGS_MODULE=comicweb.settings python core/indexing.py /home/jonas/Hämtningar/DCP\ Week\ of\ 2012-06-13/
    import sys
    if len(sys.argv)>1:
        di=DirectoryIndexer(sys.argv[1])
        di.parse(di.path)
