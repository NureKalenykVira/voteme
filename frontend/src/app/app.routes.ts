import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  {
    path: '',
    redirectTo: '/auth/register',
    pathMatch: 'full',
  },
  {
    path: 'auth',
    loadChildren: () => import('./features/auth/auth.routes').then((m) => m.AUTH_ROUTES),
  },
  {
    path: 'home',
    loadComponent: () => import('./features/home/home.component').then((m) => m.HomeComponent),
  },
  {
    path: 'profile',
    canActivate: [authGuard],
    loadChildren: () => import('./features/profile/profile.routes').then((m) => m.PROFILE_ROUTES),
  },
  {
    path: 'elections/:id/results',
    loadComponent: () =>
      import('./features/elections/pages/election-results/election-results.component').then(
        (m) => m.ElectionResultsComponent,
      ),
  },
  {
    path: 'elections',
    canActivate: [authGuard],
    loadChildren: () =>
      import('./features/elections/elections.routes').then((m) => m.ELECTIONS_ROUTES),
  },
  {
    path: 'vote/:id',
    canActivate: [authGuard],
    loadComponent: () => import('./features/vote/vote.component').then((m) => m.VoteComponent),
  },
  {
    path: 'join',
    loadComponent: () =>
      import('./features/join-voting/join-voting.component').then((m) => m.JoinVotingComponent),
  },
  {
    path: 'join/:code',
    loadComponent: () =>
      import('./features/voting-detail/voting-detail.component').then(
        (m) => m.VotingDetailComponent,
      ),
  },
  {
    path: 'my-votings',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/my-votings/my-votings.component').then((m) => m.MyVotingsComponent),
  },
  {
    path: 'event-log',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/audit/pages/event-log/event-log.component').then(
        (m) => m.EventLogComponent,
      ),
  },
  {
    path: '404',
    loadComponent: () =>
      import('./features/not-found/not-found.component').then((m) => m.NotFoundComponent),
  },
  { path: '**', redirectTo: '/404' },
];
