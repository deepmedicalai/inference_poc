import { Component } from '@angular/core';
import { RequestsService, Data } from './service';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss'],
  providers: [ RequestsService ]
})
export class AppComponent {
  private data: Data;
  private processStarted: boolean;
  private pingInterval = 5000;
  private intervalJob: any;

  constructor(private requestService: RequestsService) {
    this.resetData();
    this.processStarted = false;
  }

  resetData() {
    this.data = { stageName: '', total: 0, processedCount: 0, percent: 0, done: false }
  }

  startProcess() {
    this.requestService.startProcess()
      .subscribe(response => {
        this.processStarted = response.success
        this.resetData();
        this.pingServer();
      });
  }

  checkProcessExecution() {
    this.requestService.checkExecutionProcess()
      .subscribe(response => {
        this.data.stageName = response.stageName;
        this.data.total = response.total;
        this.data.processedCount = response.processedCount;
        this.data.percent = response.percent;
        this.data.done = response.done;
        if (this.data.done) {
          this.stopPing();
        }
      });
  }

  pingServer() {
    this.intervalJob = setInterval(_ => {
      this.checkProcessExecution();
    }, this.pingInterval);
  }

  stopPing() {
    clearInterval(this.intervalJob);
    this.processStarted = false;
  }
}
