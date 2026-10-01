import React, { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import ReactDOM from 'react-dom/client';
import { HashRouter } from './router';
import App from './App';
import { SessionProvider } from './session';
import './styles.css';
import './demo.css';

class ErrorBoundary extends Component<{children:ReactNode},{failed:boolean}> {
  state={failed:false};
  static getDerivedStateFromError(){return {failed:true};}
  componentDidCatch(error:Error,info:ErrorInfo){console.error('CityTrace render failed',error,info.componentStack);}
  render(){return this.state.failed?<div className="boot-screen"><h1>Workspace could not be displayed</h1><p>Please reload to reconnect. Your evidence is retained on the server.</p><button onClick={()=>location.reload()}>Reload workspace</button></div>:this.props.children;}
}
document.documentElement.dataset.theme='light';
import './gis.css';
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><ErrorBoundary><SessionProvider><HashRouter><App/></HashRouter></SessionProvider></ErrorBoundary></React.StrictMode>);
