import{i as r,j as e,B as h}from"./index-CzRoKttE.js";/**
 * @license lucide-react v0.363.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const p=r("Download",[["path",{d:"M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4",key:"ih7n3h"}],["polyline",{points:"7 10 12 15 17 10",key:"2ggqvy"}],["line",{x1:"12",x2:"12",y1:"15",y2:"3",key:"1vk2je"}]]);function u({data:s,filename:n,label:a="Download JSON",size:c="sm"}){const l=()=>{const d=JSON.stringify(s,null,2),i=new Blob([d],{type:"application/json"}),t=URL.createObjectURL(i),o=document.createElement("a");o.href=t,o.download=n.endsWith(".json")?n:`${n}.json`,document.body.appendChild(o),o.click(),document.body.removeChild(o),URL.revokeObjectURL(t)};return e.jsxs(h,{variant:"ghost",size:c,onClick:l,className:"print:hidden",children:[e.jsx(p,{className:"w-4 h-4 mr-2"}),a]})}export{u as D};
