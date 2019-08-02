import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse, HttpParams, HttpHeaders } from '@angular/common/http';
import { environment } from 'src/environments/environment';
import { map } from 'rxjs/operators';

export interface StartProcessResponse {
    success: boolean
}

export interface Data {
    stageName: string,
    total: number,
    processedCount: number,
    percent: number,
    done: boolean
}

@Injectable()
export class RequestsService {
    protected serverUrl: string;

    constructor(
        private http: HttpClient
    ){
        this.serverUrl = environment.baseUrl;
    }

    checkHealth() {
        return this.http.get<any>(`${this.serverUrl}${Url.health}`);
    }

    startProcess() {
        return this.http.post(`${this.serverUrl}${Url.start}`, { }).pipe(
            map((json: StartProcessResponse) => json)
        );
    }

    checkExecutionProcess() {
        return this.http.get<any>(`${this.serverUrl}${Url.check}`).pipe(
            map((json: Data) => json)
        );
    }
}

export class Url {
    public static health = '/health'
    public static start = '/start';
    public static check = '/check'
}