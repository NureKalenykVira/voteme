import { Routes } from '@angular/router';
import { AdminLayoutComponent } from './layout/admin-layout.component';

export const ADMIN_ROUTES: Routes = [
  {
    path: '',
    component: AdminLayoutComponent,
    children: [
      { path: '', redirectTo: 'users', pathMatch: 'full' },
      {
        path: 'users',
        loadComponent: () =>
          import('./pages/admin-users/admin-users.component').then(
            (m) => m.AdminUsersComponent,
          ),
      },
      {
        path: 'elections',
        loadComponent: () =>
          import('./pages/admin-elections/admin-elections.component').then(
            (m) => m.AdminElectionsComponent,
          ),
      },
      {
        path: 'statistics',
        loadComponent: () =>
          import('./pages/admin-statistics/admin-statistics.component').then(
            (m) => m.AdminStatisticsComponent,
          ),
      },
      {
        path: 'settings',
        loadComponent: () =>
          import('./pages/admin-settings/admin-settings.component').then(
            (m) => m.AdminSettingsComponent,
          ),
      },
    ],
  },
];
