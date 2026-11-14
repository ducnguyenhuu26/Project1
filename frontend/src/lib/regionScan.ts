import type { Detection, Scan } from '../types';
import type { Region } from './region';

function intersectionOverUnion(a: number[], b: number[]): number {
  const width=Math.max(0,Math.min(a[2],b[2])-Math.max(a[0],b[0]));
  const height=Math.max(0,Math.min(a[3],b[3])-Math.max(a[1],b[1]));
  const intersection=width*height;
  const areaA=Math.max(0,a[2]-a[0])*Math.max(0,a[3]-a[1]);
  const areaB=Math.max(0,b[2]-b[0])*Math.max(0,b[3]-b[1]);
  return areaA+areaB-intersection>0?intersection/(areaA+areaB-intersection):0;
}

function isDuplicate(existing: Detection, candidate: Detection): boolean {
  return existing.origin===candidate.origin&&existing.category_id===candidate.category_id&&
    !!candidate.category_id&&intersectionOverUnion(existing.bbox_xyxy,candidate.bbox_xyxy)>=0.5;
}

/** Preserve identities and skip overlapping same-class detections from a repeated ROI pass. */
export function mergeRegionScan(previous: Scan, result: Scan, box: Region, newId: () => string): { scan: Scan; added: Detection[]; duplicates: Detection[] } {
  const duplicates=previous.detections.filter(existing=>result.detections.some(candidate=>isDuplicate(existing,candidate)));
  const added: Detection[] = result.detections.length
    ? result.detections.filter(candidate=>!previous.detections.some(existing=>isDuplicate(existing,candidate)))
      .map(detection => ({...detection, id:`region-${newId()}`}))
    : [{id:`manual-region-${newId()}`,class_id:-1,category_id:null,
        label:'Vùng khoanh chưa được YOLO nhận diện',material_id:null,confidence:null,
        bbox_xyxy:box,origin:'manual',status:'unresolved',model_version:null}];
  const summary=previous.summary.map(row=>({...row,estimated_count:previous.detections.filter(d=>d.category_id===row.category_id).length}));
  for(const detection of added){
    const row=result.summary.find(item=>item.category_id===detection.category_id);
    if(!row)continue;
    const existing=summary.find(item=>item.category_id===row.category_id);
    if(existing)existing.estimated_count+=1;
    else summary.push({...row,estimated_count:1});
  }
  return {added,duplicates,scan:{...previous,detections:[...previous.detections,...added],summary,warnings:[...previous.warnings,...result.warnings]}};
}
