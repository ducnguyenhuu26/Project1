import type { Detection, Scan } from '../types';
import type { Region } from './region';

/** Preserve the original scan while appending a fresh, independently keyed ROI result. */
export function mergeRegionScan(previous: Scan, result: Scan, box: Region, newId: () => string): { scan: Scan; added: Detection[] } {
  const added: Detection[] = result.detections.length
    ? result.detections.map(detection => ({...detection, id:`region-${newId()}`}))
    : [{id:`manual-region-${newId()}`,class_id:-1,category_id:null,
        label:'Vùng khoanh chưa được YOLO nhận diện',material_id:null,confidence:null,
        bbox_xyxy:box,origin:'manual',status:'unresolved',model_version:null}];
  const summary=previous.summary.map(row=>({...row}));
  for(const row of result.summary){
    const existing=summary.find(item=>item.category_id===row.category_id);
    if(existing)existing.estimated_count+=row.estimated_count;
    else summary.push({...row});
  }
  return {added,scan:{...previous,detections:[...previous.detections,...added],summary,warnings:[...previous.warnings,...result.warnings]}};
}
