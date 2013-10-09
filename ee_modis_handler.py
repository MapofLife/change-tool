from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app


import os
import ee
import webapp2
import httplib2
import urllib
import logging
from google.appengine.api import urlfetch

import json
from oauth2client.appengine import AppAssertionCredentials

#Global variables
EE_URL = 'https://earthengine.googleapis.com'
CDB_URL = 'http://mol.cartodb.com/api/v2/sql'

# The OAuth scope URL for the Google Earth Engine API.
SCOPES = ('https://www.googleapis.com/auth/earthengine.readonly', 
          'https://www.googleapis.com/auth/earthbuilder.readonly')
SCOPES = ' '.join(SCOPES)
credentials = AppAssertionCredentials(scope=SCOPES)


class MainPage(webapp2.RequestHandler):
    def render_template(self, f, template_args):
        path = os.path.join(os.path.dirname(__file__), "templates", f)
        self.response.out.write(template.render(path, template_args))

    def get(self):

        ee.Initialize(credentials, EE_URL)

        sciname = self.request.get('sciname', None)
        habitats = self.request.get('habitats', None)
        elevation = self.request.get('elevation', None)
        year = self.request.get('year', None)
        get_area = self.request.get('get_area', 'false')
        ee_id = self.request.get('ee_id', None)
        mod_ver = self.request.get('ee_id', '5.1')
        minx =  self.request.get('minx', -179.99)
        miny =  self.request.get('miny', -89.99)
        maxx =  self.request.get('maxx', 179.99)
        maxy =  self.request.get('maxy', 89.99)



        gme_assets = {
            '2001' : 'GME/images/04040405428907908306-07899392581454566633',
            '2002' : 'GME/images/04040405428907908306-02380039866035500917',
            '2003' : 'GME/images/04040405428907908306-14600849669023874342',
            '2004' : 'GME/images/04040405428907908306-13616834228039550530',
            '2005' : 'GME/images/04040405428907908306-17457074509758683443',
            '2006' : 'GME/images/04040405428907908306-16277787816955426011',
            '2007' : 'GME/images/04040405428907908306-08517758080406137990',
            '2008' : 'GME/images/04040405428907908306-07250339350899293526',
            '2009' : 'GME/images/04040405428907908306-13736494345244774525',
            '2010' : 'GME/images/04040405428907908306-09149885918853541545',
            '2011' : 'GME/images/04040405428907908306-04204072056300184831',
	    '2012' : 'GME/images/04040405428907908306-02299466860078401645'
        }

        #Get land cover and elevation layers
        #if mod_ver == '5.0':
        #    cover = ee.Image('MCD12Q1/MCD12Q1_005_%s_01_01' % (year)).select('Land_Cover_Type_1')
        #else: 
        cover = ee.Image(gme_assets[year])
            
        elev = ee.Image('srtm90_v4')

        output = ee.Image(0)
        empty = ee.Image(0).mask(0)


        species = ee.Image(ee_id)

        #parse the CDB response


        min = int(elevation.split(',')[0])
        max = int(elevation.split(',')[1])
        habitat_list = habitats.split(",")


        output = output.mask(species)

        for pref in habitat_list:

	    if pref == 17:
		mod51pref = 0
	    else:
		mod51pref = pref
	    logging.info("habitats:%s pref: %i mod51pref: %i" % (habitats, int(pref), int(mod51pref)))
            output = output.where(cover.eq(int(mod51pref)).And(elev.gt(min)).And(elev.lt(max)),int(mod51pref))

        result = output.mask(output)

        if(get_area == 'false'):
            mapid = result.getMapId({
                'palette': 'aec3d4,152106,225129,369b47,30eb5b,387242,6a2325,c3aa69,b76031,d9903d,91af40,111149,cdb33b,cc0013,33280d,d7cdcc,f7e084,6f6f6f',
                'min':0,
		'max': 17,
                'opacity': 1
            })
            template_values = {
                'mapid' : mapid['mapid'],
                'token' : mapid['token'],
            }

            self.render_template('ee_mapid.js', template_values)
        else:
            #compute the area
          
            area = ee.call("Image.pixelArea")
            sum_reducer = ee.call("Reducer.sum")
            
            area = area.mask(species)
            total = area.mask(result.mask())
          
            region = ee.Feature(ee.Feature.Polygon([[float(minx),float(miny)],[float(minx),float(maxy)],[float(maxx),float(maxy)],[float(maxx), float(miny)], [float(minx), float(miny)]]))
            geometry = region.geometry()

            ##compute area on 1km scale
            clipped_area = total.reduceRegion(sum_reducer,geometry,5000)
            total_area = area.reduceRegion(sum_reducer,geometry,5000)

            properties = {'total': total_area, 'clipped': clipped_area}

            region = region.set(properties)

            data = ee.data.getValue({"json": region.serialize()})
            
            #self.response.headers["Content-Type"] = "application/json"
            #self.response.out.write(json.dumps(data))

            ta = 0
            ca = 0
            ta = data["properties"]["total"]["area"]
            ca = data["properties"]["clipped"]["area"]
            template_values = {
               'clipped_area': ca/1000000,
               'total_area': ta/1000000
            }

            self.render_template('ee_count.js', template_values)

application = webapp2.WSGIApplication([ ('/', MainPage), ('/.*', MainPage) ], debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
