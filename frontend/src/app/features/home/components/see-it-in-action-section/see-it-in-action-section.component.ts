import { ChangeDetectionStrategy, Component, ElementRef, signal, ViewChild } from '@angular/core';
import { TranslatePipe } from '@ngx-translate/core';
import { FaqBannerComponent } from '../../../../shared/ui/faq-banner/faq-banner.component';

@Component({
  selector: 'app-see-it-in-action-section',
  standalone: true,
  imports: [FaqBannerComponent, TranslatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './see-it-in-action-section.component.html',
  styleUrl: './see-it-in-action-section.component.scss',
})
export class SeeItInActionSectionComponent {
  readonly videoUrl =
    'https://res.cloudinary.com/dxqhrigkp/video/upload/q_auto/f_auto/v1781597446/%D0%92%D1%96%D0%B4%D0%B5%D0%BE_3%D1%85%D0%B2_hgrbi9.mp4';

  @ViewChild('videoEl') private readonly videoEl?: ElementRef<HTMLVideoElement>;

  readonly isPlaying = signal(false);

  togglePlayback(): void {
    const video = this.videoEl?.nativeElement;
    if (!video) {
      return;
    }

    if (video.paused) {
      void video.play();
    } else {
      video.pause();
    }
  }

  onVideoPlay(): void {
    this.isPlaying.set(true);
  }

  onVideoPause(): void {
    this.isPlaying.set(false);
  }

  onVideoEnded(): void {
    this.isPlaying.set(false);
  }
}
