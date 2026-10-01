import {expect,it} from 'vitest';
import {roadRoute} from './gisRoutes';
it('reverses and joins cached road geometry without a straight-line fallback',()=>{
 const data={roads:{features:[]},routes:{real_position:{C01:{lat:1,lon:1},C02:{lat:2,lon:2},C03:{lat:3,lon:3}},links:{'C01-C02':{coordinates:[[1,1],[1.8,1.4],[2,2]] as [number,number][],road_distance_km:2,straight_distance_km:1},'C02-C03':{coordinates:[[2,2],[2.3,2.8],[3,3]] as [number,number][],road_distance_km:2,straight_distance_km:1}}}};
 expect(roadRoute(data,'C03','C01')).toEqual([[3,3],[2.3,2.8],[2,2],[1.8,1.4],[1,1]]);
 expect(roadRoute(data,'C01','unknown')).toEqual([]);
});
