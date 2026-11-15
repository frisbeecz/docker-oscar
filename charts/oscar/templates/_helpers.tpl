{{/* SPDX-License-Identifier: Apache-2.0 */}}
{{- define "oscar.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- define "oscar.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "oscar.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- define "oscar.selectorLabels" -}}
app.kubernetes.io/name: {{ include "oscar.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
{{- define "oscar.labels" -}}
{{ include "oscar.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | quote }}
{{- end -}}
{{- define "oscar.claimName" -}}
{{- $settings := index .root.Values.persistence .role -}}
{{- if $settings.existingClaim -}}
{{- $settings.existingClaim -}}
{{- else -}}
{{- $suffix := printf "-%s-v2" .role -}}
{{- printf "%s%s" (include "oscar.fullname" .root | trunc (int (sub 63 (len $suffix))) | trimSuffix "-") $suffix -}}
{{- end -}}
{{- end -}}
{{- define "oscar.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "oscar.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}
{{- define "oscar.validateMounts" -}}
{{- $names := dict "config" true "data" true "sdcard" true "shm" true -}}
{{- $paths := dict -}}
{{- range .Values.extraPvcMounts -}}
{{- if or (hasKey $names .name) (hasKey $paths .mountPath) (contains ".." .mountPath) -}}
{{- fail "extraPvcMounts names and mountPaths must be unique, non-reserved, and contain no '..'" -}}
{{- end -}}
{{- $_ := set $names .name true -}}
{{- $_ := set $paths .mountPath true -}}
{{- end -}}
{{- end -}}
