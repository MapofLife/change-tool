"""This module executes area calculations for all modis years"""

__author__ = 'Jeremy Malczyk'

# Standard Python imports
import webapp2
import urllib
import logging
import json
import cache


# Google App Engine imports
from google.appengine.api import urlfetch
from google.appengine.ext.webapp.util import run_wsgi_app


class ChangeAPI(webapp2.RequestHandler):
    def get(self):
        
        self.area_results = [['Year','Refined Range Area (sq km)']]
        self.pop_results = [['Year','Population within Range', 'Population within Refined Range']]
        
        self.mapid_results = {}
        self.rpcs = []

        self.url = self.request.host_url + '/api/year?%s'
        self.callback = self.request.get('callback',None)
        self.habitats = self.request.get('habitats', None)
        self.elevation = self.request.get('elevation', None)
        self.ee_id = self.request.get('ee_id', None)
        self.get_area = self.request.get('get_area', 'true')
        self.minx = self.request.get('minx', -179.9)
        self.miny = self.request.get('miny', -89.9)
        self.maxx = self.request.get('maxx', 179.9)
        self.maxy = self.request.get('maxy', 89.9)
        self.call_ver = self.request.get('call_ver',None)
        self.mapid_results['call_ver']= self.call_ver
        
        logging.info('Firing requests for 2001 to 2013')
        for i in range(2001,2013):
            year_url = self.url % (
                urllib.urlencode(
                    dict(habitats=self.habitats, 
                         elevation=self.elevation, 
                         year=i, 
                         ee_id=self.ee_id, 
                         get_area=self.get_area,
                         minx=self.minx,
                         miny=self.miny,
                         maxx=self.maxx,
                         maxy=self.maxy
                    )
                )
            )
            rpc = urlfetch.create_rpc(deadline=480)
            rpc.callback = self.create_callback(rpc, i)
            logging.info('Calling %s' % year_url)
            urlfetch.make_fetch_call(rpc, year_url)
            self.rpcs.append(rpc)
        
        for rpc in self.rpcs:
            rpc.wait()
    def handle_result(self, rpc, year):
        #logging.info("%i called back! %s" % (int(year), rpc.get_result().content))
        result = rpc.get_result()
        try:
           if result.status_code == 200 and self.get_area == 'true' :
               record = json.loads(result.content)
               self.area_results.append([
                     year,
                     record["clipped_area"]
               ])
               self.pop_results.append([
                     year,                   
                     record["total_pop"],
                     record["clipped_pop"]
               ])
               if len(self.area_results) > len(self.rpcs):
                   if self.callback is not None:
                       self.response.out.write(
                        '%s(%s);' % (self.callback, json.dumps({'area': self.area_results, 'pop' : self.pop_results, 'call_ver' : self.call_ver})))
                   else:
                       self.response.out.write(
                            json.dumps({'area': self.area_results, 'pop' : self.pop_results, 'call_ver' : self.call_ver}))
           else:
               self.mapid_results["modis_%s" % year] = json.loads(result.content)
               if len(self.mapid_results) > len(self.rpcs):
                   if self.callback is not None:
                       self.response.out.write(
                        '%s(%s);' % (self.callback, json.dumps(self.mapid_results)))

                   else:
                       self.response.out.write(json.dumps(self.mapid_results))
               
        except urlfetch.DownloadError:
            logging.error("Ruh roh.")

    def create_callback(self,rpc, year):
        return lambda: self.handle_result(rpc, year)
   
application = webapp2.WSGIApplication(
    [('/api/change', ChangeAPI)],
    debug=False)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
