{{/*
_helpers.tpl — LIP Helm chart template helpers
*/}}

{{- define "lip.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "lip.fullname" -}}
{{- printf "%s-%s" .Chart.Name .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "lip.namespace" -}}
{{- .Values.namespace | default "lip" }}
{{- end }}

{{/* Common labels applied to all resources */}}
{{- define "lip.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
lip/platform: "true"
{{- end }}

{{/* Selector labels for a given component */}}
{{- define "lip.selectorLabels" -}}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/instance: {{ .release }}
{{- end }}

{{/* Image string for a component */}}
{{- define "lip.image" -}}
{{- printf "%s/%s:%s" .registry .image .tag }}
{{- end }}
