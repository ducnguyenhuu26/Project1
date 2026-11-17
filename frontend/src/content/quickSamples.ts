export type QuickSample = {
  id: string;
  image: string;
  fileName: string;
  titleVi: string;
  titleEn: string;
  detailVi: string;
  detailEn: string;
};

export const quickSamples: QuickSample[] = [
  {id:'bottle',image:'/quick-samples/plastic-bottle.jpg',fileName:'plastic-bottle.jpg',titleVi:'Chai nhựa',titleEn:'Plastic bottle',detailVi:'Một vật thể · nhựa',detailEn:'One object · plastic'},
  {id:'cardboard',image:'/quick-samples/cardboard-box.jpg',fileName:'cardboard-box.jpg',titleVi:'Thùng carton',titleEn:'Cardboard box',detailVi:'Một vật thể · giấy / bìa',detailEn:'One object · paper / cardboard'},
  {id:'mixed',image:'/quick-samples/mixed-packaging.jpg',fileName:'mixed-packaging.jpg',titleVi:'Nhiều vật thể',titleEn:'Multiple objects',detailVi:'Carton và túi nhựa',detailEn:'Cardboard and plastic bags'},
];
