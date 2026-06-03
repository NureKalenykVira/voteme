import { Component, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { ToastComponent } from './shared/ui/toast/toast.component';
import { GlobalModalComponent } from './shared/components/global-modal/global-modal.component';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, ToastComponent, GlobalModalComponent],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App {
  protected readonly title = signal('frontend');
}
