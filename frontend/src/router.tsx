import { Children, createContext, isValidElement, useContext, useEffect, useMemo, useState } from 'react';
import type { AnchorHTMLAttributes, ReactNode, ReactElement } from 'react';
interface Location {pathname:string;search:string;state:unknown}
function readLocation():Location{const url=new URL(location.hash.slice(1)||'/',location.origin);return {pathname:url.pathname,search:url.search,state:history.state};}
const Context=createContext<Location>({pathname:'/',search:'',state:null});
export function HashRouter({children}:{children:ReactNode}){const [value,setValue]=useState(readLocation);useEffect(()=>{const sync=()=>setValue(readLocation());window.addEventListener('popstate',sync);window.addEventListener('hashchange',sync);window.addEventListener('citytrace:navigate',sync);return()=>{window.removeEventListener('popstate',sync);window.removeEventListener('hashchange',sync);window.removeEventListener('citytrace:navigate',sync);};},[]);return <Context.Provider value={value}>{children}</Context.Provider>;}
export const useLocation=()=>useContext(Context);
export function useNavigate(){return (to:string,options?:{state?:unknown;replace?:boolean})=>{history[options?.replace?'replaceState':'pushState'](options?.state||null,'',`/#${to}`);window.dispatchEvent(new Event('citytrace:navigate'));};}
export function useSearchParams(){const l=useLocation();return [useMemo(()=>new URLSearchParams(l.search),[l.search])] as const;}
export function useParams(){const l=useLocation();return {id:l.pathname.match(/^\/vehicles\/([^/]+)/)?.[1]};}
export function Link({to,state,onClick,children,...props}:Omit<AnchorHTMLAttributes<HTMLAnchorElement>,'href'> & {to:string;state?:unknown;children:ReactNode}){const navigate=useNavigate();return <a {...props} href={`/#${to}`} onClick={e=>{onClick?.(e);if(e.defaultPrevented||e.ctrlKey||e.metaKey||e.shiftKey||e.altKey||e.button!==0)return;e.preventDefault();navigate(to,{state});}}>{children}</a>;}
export function NavLink({to,className,children,...props}:{to:string;className?:(args:{isActive:boolean})=>string;children:ReactNode;end?:boolean}){const l=useLocation(),active=l.pathname===to;return <Link to={to} className={className?.({isActive:active})} aria-current={active?'page':undefined} {...(props.end?{}:{})}>{children}</Link>;}
export function Navigate({to,replace}:{to:string;replace?:boolean}){useEffect(()=>{history[replace?'replaceState':'pushState'](null,'',`/#${to}`);window.dispatchEvent(new Event('citytrace:navigate'));},[to,replace]);return null;}
interface RouteProps {path:string;element:ReactNode}
export function Route(_props:RouteProps){return null;}
export function Routes({children,location:override}:{children:ReactNode;location?:Location}){const current=useLocation(),pathname=(override||current).pathname,all=Children.toArray(children).filter(isValidElement) as ReactElement<RouteProps>[];return all.find(c=>c.props.path!=='*'&&new RegExp('^'+c.props.path.replace(/:[^/]+/g,'[^/]+')+'$').test(pathname))?.props.element||all.find(c=>c.props.path==='*')?.props.element||null;}
