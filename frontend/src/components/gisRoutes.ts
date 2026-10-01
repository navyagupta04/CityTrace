import type {RealRoadData} from '../real/RoadLayer';
export type Coordinate=[number,number];
// Each cached edge is routed along the OSM network. Missing direct pairs use
// a shortest path through cached edges; never substitute a straight line.
export function roadRoute(data:RealRoadData|null,from:string,to:string):Coordinate[]{
 if(!data)return [];
 const links=data.routes.links,direct=links[`${from}-${to}`],reverse=links[`${to}-${from}`];
 if(direct)return direct.coordinates;
 if(reverse)return [...reverse.coordinates].reverse();
 const pending=new Set(Object.keys(data.routes.real_position)),distance=new Map<string,number>([[from,0]]),previous=new Map<string,string>();
 while(pending.size){
  const node=[...pending].sort((a,b)=>(distance.get(a)??Infinity)-(distance.get(b)??Infinity))[0];
  if(!Number.isFinite(distance.get(node)))break;
  pending.delete(node);if(node===to)break;
  for(const [key,edge] of Object.entries(links)){
   const [a,b]=key.split('-'),next=a===node?b:b===node?a:null;if(!next||!pending.has(next))continue;
   const score=distance.get(node)!+edge.road_distance_km;
   if(score<(distance.get(next)??Infinity)){distance.set(next,score);previous.set(next,node);}
  }
 }
 if(!previous.has(to))return [];
 const ids=[to];while(ids[0]!==from)ids.unshift(previous.get(ids[0])!);
 return ids.slice(1).flatMap((id,i)=>{const points=links[`${ids[i]}-${id}`]?.coordinates||[...links[`${id}-${ids[i]}`].coordinates].reverse();return i?points.slice(1):points;});
}
