import { Routes } from '@angular/router';

export const ELECTIONS_ROUTES: Routes = [
  {
    path: 'create',
    loadComponent: () =>
      import('./pages/create-voting/create-voting.component').then((m) => m.CreateVotingComponent),
  },
  {
    path: ':id/edit',
    loadComponent: () =>
      import('./pages/create-voting/create-voting.component').then((m) => m.CreateVotingComponent),
  },
  {
    path: ':id/invite',
    loadComponent: () => import('./pages/invite/invite.component').then((m) => m.InviteComponent),
  },
  {
    path: ':id/voters',
    loadComponent: () =>
      import('./pages/manage-voters/manage-voters.component').then((m) => m.ManageVotersComponent),
  },
  {
    path: '',
    redirectTo: 'create',
    pathMatch: 'full',
  },
];
