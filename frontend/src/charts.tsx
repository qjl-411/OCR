import { Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Dashboard } from './types'
import { yuan } from './api'
import { Empty } from './components'

export const COLORS=['#27765a','#8db8a5','#b3cddf','#c9b3dd','#e9ba7b']
export function TrendChart({data}:{data:Dashboard['trend']}) {
  const filled: Dashboard['trend']=[]
  if(data.length) {
    const last=data[data.length-1].month; const y=Number(last.slice(0,4)),m=Number(last.slice(5))-1
    for(let offset=5;offset>=0;offset--){const d=new Date(y,m-offset,1);const key=`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;filled.push(data.find(x=>x.month===key)||{month:key,amount:0,count:0})}
  }
  if(!filled.length) return <Empty title="暂无已确认支出" text="完成票据复核后，支出趋势会显示在这里。"/>
  return <div className="trend-chart" role="img" aria-label={'近六个月已确认支出趋势：'+filled.map(x=>`${x.month} ${yuan(x.amount)}元`).join('，')}><ResponsiveContainer width="100%" height="100%"><AreaChart data={filled} margin={{top:15,right:15,left:0,bottom:0}}><defs><linearGradient id="spend" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#2d8665" stopOpacity={.18}/><stop offset="95%" stopColor="#2d8665" stopOpacity={.015}/></linearGradient></defs><CartesianGrid strokeDasharray="4 5" vertical={false} stroke="#e9eeeb"/><XAxis dataKey="month" tickFormatter={v=>`${Number(v.slice(5))}月`} axisLine={false} tickLine={false} dy={9} tick={{fill:'#718079',fontSize:13}}/><YAxis tickFormatter={v=>v>=1000?`${v/1000}k`:v} axisLine={false} tickLine={false} width={44} tick={{fill:'#819087',fontSize:12}}/><Tooltip formatter={(v:number)=>[`¥ ${yuan(v)}`,'已确认支出']} labelFormatter={v=>`${v}`} contentStyle={{borderRadius:12,border:'1px solid #e1e9e4',fontSize:14,boxShadow:'0 4px 20px #183d2812'}}/><Area type="monotone" dataKey="amount" stroke="#2c7b5b" strokeWidth={2.5} fill="url(#spend)" activeDot={{r:5,strokeWidth:3,stroke:'#fff'}} isAnimationActive={false}/></AreaChart></ResponsiveContainer></div>
}
export function CategoryChart({data,count}:{data:Dashboard['categories'];count:number}) {
  const total=data.reduce((s,x)=>s+x.amount,0)
  if(!data.length)return <Empty title="暂无分类统计" text="统计仅包含已确认票据。"/>
  return <div className="category-chart"><div className="donut-wrap" role="img" aria-label={data.map(x=>`${x.name} ${yuan(x.amount)}元`).join('，')}><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={data} dataKey="amount" nameKey="name" innerRadius={61} outerRadius={79} paddingAngle={3} stroke="none" isAnimationActive={false}>{data.map((_,i)=><Cell key={i} fill={COLORS[i%COLORS.length]}/>)}</Pie><Tooltip formatter={(v:number)=>`¥ ${yuan(v)}`} contentStyle={{borderRadius:10,fontSize:14}}/></PieChart></ResponsiveContainer><div className="donut-center"><strong>{count}<small> 张</small></strong><span>已确认票据</span></div></div><div className="category-legend">{data.map((c,i)=><div key={c.name}><span className="legend-label"><i style={{background:COLORS[i%COLORS.length]}}/>{c.name}</span><span className="legend-value">{total?Math.round(c.amount/total*100):0}%</span></div>)}</div></div>
}
