from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app


import os
import ee
import config
import webapp2
import httplib2
import urllib
import logging
from google.appengine.api import urlfetch

import json
from oauth2client.appengine import AppAssertionCredentials

EE_TILE_URL = 'https://earthengine.googleapis.com/map/%s/{Z}/{X}/{Y}?token=%s'

class AssessHandler(webapp2.RequestHandler):
    def render_template(self, f, template_args):
        path = os.path.join(os.path.dirname(__file__), "templates", f)
        self.response.out.write(template.render(path, template_args))

    def getRandomPoints(self,sciname):
        cdburl = 'https://mol.cartodb.com/api/v1/sql?q=%s'
        sql = "Select " \
            "ST_X(ST_Transform(the_geom_webmercator,4326)) as lon, " \
            "ST_Y(ST_Transform(the_geom_webmercator,4326)) as lat " \
            "FROM get_tile_beta('gbif_aug_2013','%s',1995,2015) " \
            "order by random() limit 1000"
        
        qstr = urllib.quote_plus((sql % (sciname)))
        url = cdburl % (qstr)
        logging.info(url)
        points = urlfetch.fetch(url)
        return points.content
        
    def get(self):

        ee.Initialize(config.EE_CREDENTIALS, config.EE_URL)

        sciname = self.request.get('sciname', None)
        habitats = self.request.get('habitats', None)
        elevation = self.request.get('elevation', None)
        year = self.request.get('year', None)
        mode = self.request.get('mode', 'area')
        ee_id = self.request.get('ee_id', None)
        minlng = self.request.get('minx', None)
        maxlng = self.request.get('maxx', None)
        minlat = self.request.get('miny', None)
        maxlat = self.request.get('maxy', None)
        
        
        #Get land cover and elevation layers
        cover = ee.Image('MCD12Q1/MCD12Q1_005_%s_01_01' % 
                         (year)).select('Land_Cover_Type_1')
                         
        elev = ee.Image('GME/images/04040405428907908306-08319720230328335274')
        #elev = ee.Image('srtm90_v4')
        #minlat = round(extent["sw"]["lat"]*1000)/1000
        
        #minlng = round(extent["sw"]["lng"]*1000)/1000
        
        #maxlat = round(extent["ne"]["lat"]*1000)/1000
        
        #maxlng = round(extent["ne"]["lng"]*1000)/1000
    
        #define a bounding polygon for the reducers
       
        region = ee.Feature(
            ee.Feature.Polygon([
                [float(minlng),float(minlat)],
                [float(minlng),float(maxlat)],
                [float(maxlng),float(maxlat)],
                [float(maxlng),float(minlat)],
                [float(minlng),float(minlat)]
            ])
        )
        geometry = region.geometry()
        
       
        output = ee.Image(0)
        empty = ee.Image(0).mask(0)

        species = ee.Image(ee_id)
        
        
        
        #parse the CDB response

        min = int(elevation.split(',')[0])
        max = int(elevation.split(',')[1])
        habitat_list = habitats.split(",")

        output = output.mask(species)

        for pref in habitat_list:
            for year in range(2001,2010):
                cover = ee.Image('MCD12Q1/MCD12Q1_005_%s_01_01' % 
                             (year)).select('Land_Cover_Type_1')
                output = output.where(
                    cover.eq(int(pref)).And(elev.gt(min)).And(elev.lt(max)),1)

        result = output.mask(output)

        if mode == 'range':
            
            rangeMap = result.getMapId({
                'palette': '000000,85AD5A',
                'max': 1,
                'opacity': 0.8
            })
            response = {
                'maps' : [
                    EE_TILE_URL % 
                         (rangeMap['mapid'], rangeMap['token'])
                    
                ]
            }
            self.response.headers["Content-Type"] = "application/json"
            self.response.out.write(json.dumps(response))
        elif mode == 'assess':
            pointjson = self.getRandomPoints(sciname)
            pjson = json.loads(pointjson)
            
            logging.info(json.dumps(pjson))
            
            if pjson["total_rows"] == 0:
               self.response.headers["Content-Type"] = "application/json"
               self.response.out.write(json.dumps({
                                        "has_pts" : False
                                        }
                                       ))    
            else:
                #Create an array of Points
                pts = []
                for row in pjson["rows"]:
                    pts.append(
                       ee.Feature(
                          ee.Feature.Point(
                             row["lon"],row["lat"]),
                             {'val':0 }))
                
                #Create a FeatureCollection from that array 
                pts_fc = ee.FeatureCollection(pts)
                logging.info('Created the point FC')
                #this code reduces the point collection to an image.  Each pixel 
                #contains a count for the number of pixels that intersect with it
                #then, the point count image is masked by the range
                #imgPoints = pts_fc.reduceToImage(['val'], ee.call('Reducer.sum')).mask(result);
                #imgOutPoints = pts_fc.reduceToImage(['val'], ee.call('Reducer.sum')).mask(result.neq(1));
                #now, just sum up the points image.  this is the number of points that overlap the range
                #ptsIn = imgPoints.reduceRegion(ee.call('Reducer.sum'), geometry, 10000)
                
                #This would be for making pts_in and pts_out FeatureCollections 
                #that can be mapped in different colors. Doesn't work...
                #ptsInFC = imgPoints.reduceToVectors(None,None,100000000)
                #ptsOutFC = imgOutPoints.reduceToVectors(None, None, 100000000)
                
                #data = ee.data.getValue({"json": ptsIn.serialize()})
                #pts_in = data["sum"]
                
                #Sample the range map image
                coll = ee.ImageCollection([result])
                logging.info('Sample the image')
                sample = coll.getRegion(pts_fc,10000).getInfo()
                logging.info('Sampled it')
                #Create a FC for the points that fell inside the range
                pts_in = []
                for row in sample[1:]:
                    pts_in.append(
                        ee.Feature(
                            ee.Feature.Point(row[1], row[2]),{'val': 1})
                    )
                
                pts_in_fc = ee.FeatureCollection(pts_in)
                
                #reverse Join to get the ones that are outside the range
                pts_out_fc = pts_fc.groupedJoin(
                    pts_in,'within_distance',distance=10000,mode='inverted')
                
                pts_out_map = pts_out_fc.getMapId({'color': 'e02070'})
                pts_in_map = pts_in_fc.getMapId({'color': '007733'})
                
                response = {
                    'maps' : [
                        EE_TILE_URL % 
                             (pts_in_map['mapid'],pts_in_map['token']),
                        EE_TILE_URL % 
                             (pts_out_map['mapid'],pts_out_map['token'])
                        
                    ],
                    'has_pts' : True,
                    'pts_in' : len(pts_in),
                    'pts_tot' : len(pts)
                    # add points stats to result
                }
                self.response.headers["Content-Type"] = "application/json"
                self.response.out.write(json.dumps(response))
        else:
        #compute the area
          
            area = ee.call("Image.pixelArea")
            sum_reducer = ee.call("Reducer.sum")
            
            area = area.mask(species)
            total = area.mask(result.mask())

            ##compute area on 10km scale
            clipped_area = total.reduceRegion(
                sum_reducer,geometry,scale=1000,bestEffort=True)
            total_area = area.reduceRegion(
                sum_reducer,geometry,scale=1000,bestEffort=True)

            properties = {'total': total_area, 'clipped': clipped_area}

            region = region.set(properties)

            data = ee.data.getValue({"json": region.serialize()})
            logging.info(json.dumps(data))
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
            self.response.headers["Content-Type"] = "application/json"
            self.response.out.write(json.dumps(template_values))
            
application = webapp2.WSGIApplication(
    [ ('/api/assess', AssessHandler)], debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
