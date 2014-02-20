from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import urlfetch

import mol_assets
import os
import ee
import webapp2
import urllib
import logging
import json
import config

class YearHandler(webapp2.RequestHandler):
    def get(self):

        ee.Initialize(config.EE_CREDENTIALS, config.EE_URL)
        
        # Gather http req params
        sciname = self.request.get('sciname', None)
        habitats = self.request.get('habitats', None)
        elevation = self.request.get('elevation', None)
        year = self.request.get('year', None)
        get_area = self.request.get('get_area', 'false')
        ee_id = self.request.get('ee_id', None)
        minx = self.request.get('minx', -179.99)
        miny = self.request.get('miny', -89.99)
        maxx = self.request.get('maxx', 179.99)
        maxy = self.request.get('maxy', 89.99)

        # Get images for the year of interest
        cover = ee.Image(mol_assets.modis51[year])
        elev = ee.Image(mol_assets.elevation)        
        pop = ee.Image(mol_assets.population[year])
        pop = pop.mask(pop.lt(0))
        # Get the species range map
        species = ee.Image(ee_id)

        # Elevation range and habitats for this species 
        min = int(elevation.split(',')[0])
        max = int(elevation.split(',')[1])
        habitat_list = habitats.split(",")


        output = ee.Image(0).mask(species)

        for pref in habitat_list:
            if pref == 17:
                mod51pref = 0
            else:
                mod51pref = pref
            
            output = output.where(
                cover.eq(int(mod51pref)).And(elev.gt(min)).And(elev.lt(max)),
                int(mod51pref)
            )

        result = output.mask(output)

        if(get_area == 'false'):
            
            # just return Map ID's
            map = result.getMapId({
                'palette': 'aec3d4,152106,225129,369b47,30eb5b,387242,6a2325,'\
                        'c3aa69,b76031,d9903d,91af40,111149,cdb33b,cc0013,'\
                        '33280d,d7cdcc,f7e084,6f6f6f',
                'min':0,
                'max': 17,
                'opacity': 1
            })
            getTileUrl = 'https://earthengine.googleapis.com/'\
                'map/%s/{Z}/{X}/{Y}?token=%s' % (
                    map['mapid'],
                    map['token']
                )


            self.response.out.write(json.dumps(getTileUrl))
        else:
            # compute the area and population
            area = ee.call("Image.pixelArea")
            sum_reducer = ee.call("Reducer.sum")
            
            area = area.mask(species)
            total = area.mask(result.mask())
          
            pop = pop.mask(species)
            pop = pop.where(pop.lt(0),0)
            
           # Generate a region to do the calculation over
            region = ee.Feature(
                ee.Feature.Polygon(
                    [[float(minx), float(miny)],
                     [float(minx), float(maxy)],
                     [float(maxx), float(maxy)],
                     [float(maxx), float(miny)],
                     [float(minx), float(miny)]
                     ]))
            geometry = region.geometry()

            # #compute area on 1km scale
            clipped_area = total.reduceRegion(
                sum_reducer, geometry, maxPixels=10000000000)
            total_pop = pop.reduceRegion(
                sum_reducer, geometry, maxPixels=10000000000)
            
            properties = {
                'clipped_area': clipped_area,
                'total_pop': total_pop,
            }

            region = region.set(properties)

            data = ee.data.getValue({"json": region.serialize()})
            data = data["properties"]
            species_stats = {
               'clipped_area': round(
                    (data["clipped_area"]["area"]) / 1000000, 3),
               'total_pop': round(
                    data["total_pop"]["b1"], 0)
            }

            self.response.out.write(
                json.dumps(species_stats)
            )
            
application = webapp2.WSGIApplication(
    [ ('/api/year', YearHandler)], debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
