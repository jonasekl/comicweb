#-*- coding: latin-1*-

# -- standard imports
import os,json,traceback,logging,simplejson
import zipfile,rarfile
from datetime import datetime

# -- django imports
from django.contrib.auth.models import User
from django.db import models

# --- project imports
import indexing

# --- globals
logger = logging.getLogger('comicweb.core.models')

# -- These data classes pretty much map to comicvine's data classes.

class Issue(models.Model):
    ''' A single issue  '''
    # TODO: currently totally lacks creator credits
    name = models.CharField(max_length=255, blank=True)
    description = models.TextField()
    cvid = models.IntegerField()
    cv_api_detail_url = models.URLField()
    characters = models.ManyToManyField('Character')
    issue_number = models.FloatField()
    locations = models.ManyToManyField('Location')
    publish_month = models.IntegerField(blank=True, null=True)
    publish_year = models.IntegerField(blank=True, null=True)
    site_detail_url = models.URLField()
    story_arcs = models.ManyToManyField('StoryArc')
    teams = models.ManyToManyField('Team')
    volume = models.ForeignKey('Volume')
    # creator credits
#    letterer = models.ForeignKey('Creator', null=True, blank=True)
#    colorist = models.ForeignKey('Creator', null=True, blank=True)
#    writer = models.ForeignKey('Creator', null=True, blank=True)
#    penciller = models.ForeignKey('Creator', null=True, blank=True)
#    penciller = models.ForeignKey('Creator', null=True, blank=True)

    # custom fields
    age_rating = models.ForeignKey('AgeRating', blank=True, null=True)
#models.CharField(max_length=10, blank=True, null=True)

    def __unicode__(self):
        return u'%s %s' % (self.volume.name, str(self.issue_number))

    # NOTE: This currently simply returns the first available material
    def get_material(self):
        try:
            materials = Material.objects.filter(issue=self)
            if materials:
                logger.debug('Issue %s has the following material %s' % (self, materials))
                return materials[0]
            else:
                return None
        except:
            return None


    def get_next(self):
        try:
            next_issue = Issue.objects.get(volume=self.volume, issue_number=self.issue_number+1)
            return next_issue
        except:
            return None    

    def get_previous(self):
        try:
            prev_issue = Issue.objects.get(volume=self.volume, issue_number=self.issue_number-1)
            return prev_issue
        except:
            return None

    def register_reading(self, user, page):
        try:
            reading = Reading.objects.get(user=user, issue=self)
            reading.when = datetime.now()
            reading.page = page
            reading.save()
            logger.debug('updating reading %s' % (reading))
        except:
            logger.debug('no reading found for issue %s and user %s, registering new ' % (self, user))
            Reading(user=user, issue=self, page=page).save()

    def get_latest_reading(self, user):
        try:
            return Reading.objects.filter(user=user, issue=self).latest('id')
        except:
#            logger.debug(traceback.format_exc())
            return None


class Volume(models.Model):
    cv_api_detail_url = models.URLField()
    concepts = models.ManyToManyField('Concept', null=True, blank=True)
    description = models.TextField()
    cvid = models.IntegerField()
    name = models.CharField(max_length=255)
    publisher = models.ForeignKey('Publisher')
    start_year = models.IntegerField(blank=True, null=True)
    age_rating = models.ForeignKey('AgeRating', blank=True, null=True)

    def __unicode__(self):
        return u'%s' % (self.name)

    def get_latest_issue(self):
        try:
            return Issue.objects.filter(volume=self).latest('issue_number')
        except:
            logger.warn('unable to get the latest issue for volume %s:\n%s' % (self, traceback.format_exc()))
            
            return None

    def is_ongoing(self):
        try:
            _now = datetime.now()
            _latest_issue = self.get_latest_issue()
            if _latest_issue is not None and int(_latest_issue.publish_year) == _now.year and int(_latest_issue.publish_month) > (_now.month-4) and len(Issue.objects.filter(volume=self)) > 1:
                return True
            else:
                return False
        except:
            logger.warn(traceback.format_exc())
            return False

    def list_missing_issues(self, start, stop):
        ret = []
        while start<stop:
            ret.append(start)
            start+=1
        return ret
    
    def check_missing_issues(self):
        issues = self.issue_set.order_by('issue_number')
        missing_issue_numbers = []
        for i in range(len(issues)):
            if i > 0:
                expected_issue = float(issues[i-1].issue_number+1.0)
                actual_issue = float(issues[i].issue_number)
                if actual_issue != expected_issue:
                    logger.info('Missing issue(s) for %s! expected:%s, actual:%s' % (self, str(expected_issue), str(actual_issue)))
                    number_of_missing = actual_issue - expected_issue 
                    logger.info('%d issues appear to be missing' % number_of_missing )
                    missing_issue_numbers += self.list_missing_issues( expected_issue,  actual_issue)
                    logger.info('missing_issues for %s :%s' % (self, missing_issue_numbers) )
        return missing_issue_numbers

class StoryArc(models.Model):
    cvid = models.IntegerField()
    cv_api_detail_url = models.URLField()
    name = models.CharField(max_length=255)
    deck = models.CharField(max_length=1024)
    description = models.TextField()
    def __unicode__(self):
        return u'%s' % (self.name)

class Concept(models.Model):
    cvid = models.IntegerField()
    cv_api_detail_url = models.URLField()
    name = models.CharField(max_length=255)
    deck = models.CharField(max_length=1024)
    description = models.TextField()

    def __unicode__(self):
        return u'%s' % self.name

class Publisher(models.Model):
    cvid = models.IntegerField()
    cv_api_detail_url = models.URLField()
    name = models.CharField(max_length=50)
    deck = models.CharField(max_length=1024)
    description = models.TextField()

    def __unicode__(self):
        return u'%s' % self.name

class Character(models.Model):
    cvid = models.IntegerField()
    cv_api_detail_url = models.URLField()
    name = models.CharField(max_length=255)
    description = models.TextField()
    real_name = models.CharField(max_length=255)

    def __unicode__(self):
        return u'%s' % self.name

class Team(models.Model):
    cvid = models.IntegerField()
    cv_api_detail_url = models.URLField()
    name = models.CharField(max_length=50)
    deck = models.CharField(max_length=1024)
    description = models.TextField()
    publisher = models.ForeignKey(Publisher)
    characters = models.ManyToManyField(Character)

    def __unicode__(self):
        return u'%s' % self.name

class Location(models.Model):
    cvid = models.IntegerField()
    cv_api_detail_url = models.URLField()
    name = models.CharField(max_length=255)
    deck = models.CharField(max_length=1024)
    description = models.TextField()

    def __unicode__(self):
        return u'%s' % self.name


class Creator(models.Model):
    "Writer or artist"
    firstname = models.CharField(max_length=255, null=True, blank=True)
    lastname = models.CharField(max_length=255, null=True, blank=True)
    comment = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return '%s %s' % (self.firstname, self.lastname)

# -- other data

class Material (models.Model):
    file = models.CharField(max_length=1024)
    issue = models.ForeignKey(Issue, blank=True, null=True)
    added_on = models.DateTimeField(default=datetime.now)
    def __unicode__(self):
        return u'(#%d)%s' % (self.id, self.file)
    def get_filename(self):
        if self.issue:
            return '%s %d.%s' % (self.issue.volume.name, self.issue.issue_number, self.file[self.file.rfind('.')+1:])
        else:
            return self.file[self.file.rfind('/')+1:]

    def _open(self):
        try:
            if 'cbr' in self.file.lower():
                comicfile = rarfile.RarFile(self.file, 'r')
                filelist = sorted([x for x in comicfile.namelist() if '.' in x])
                return comicfile
            else:
                return zipfile.ZipFile(self.file, 'r')
        except:
            logger.error('Unable to open material %s:\n%s' % (self, traceback.format_exc()))
            return None

    def get_page( self, page_number ):
        
        if 'cbr' in self.file.lower():
            comicfile = rarfile.RarFile(self.file, 'r')
            filelist = sorted([x for x in comicfile.namelist() if '.' in x])
            return comicfile.read( filelist[int(page_number)] )
        else:
            comicfile = zipfile.ZipFile(self.file, 'r')
            return comicfile.open(comicfile.filelist[int(page_number)]).read()

    def get_pagecount(self):
        book = self._open()
        return len( sorted([x for x in book.namelist() if '.' in x]) ) if type(book) == rarfile.RarFile else len(book.filelist)

    def get_potential_volumes(self):
        ''' attempts to create an Issue by looking up on comicvine '''
        # TMP
##        return []
        _book_file = indexing.BookFile(self.file)
        #_book_file.lookup()
        _volumes = _book_file.get_potential_volumes()
        for _vol in _volumes:
            _vol['subset_issues'] = _vol['issues'][-10:]
        return _volumes


class Reading (models.Model):
    user = models.ForeignKey(User)
    issue = models.ForeignKey(Issue)
    page = models.IntegerField(default=0)
    when = models.DateTimeField(default=datetime.now)

    def __unicode__(self):
        return u'%s %s@%d' % (self.user, self.issue, self.page)

def get_recent_list_old( user ):
    try:
        ret = []
        volumes = []
        for r in Reading.objects.filter(user=user).order_by('when').reverse():
            if not r.issue.volume in volumes:
                volumes.append(r.issue.volume)
                ret.append(r)
        return ret
    except:
        return None


class List (models.Model):
    user = models.ForeignKey(User)
    created = models.DateTimeField(default=datetime.now)
    name = models.CharField(max_length=50)

    def pop(self, entry):
        pass

    def push(self, entry):
        pass
    def __unicode__(self):
        return u'%s' % (self.name)

class ListEntry (models.Model):
    list = models.ForeignKey(List)
    issue = models.ForeignKey(Issue)
    place = models.IntegerField()
    def __unicode__(self):
        return u'%s' % self.issue

class AgeRating( models.Model ):
    text = models.CharField(max_length=25)
    description = models.TextField(blank=True, null=True)
    def __unicode__(self):
        return u'%s' % self.text
