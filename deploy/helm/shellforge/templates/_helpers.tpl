{{/* Common labels */}}
{{- define "shellforge.labels" -}}
app.kubernetes.io/name: shellforge
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{- define "shellforge.controlPlane.fullname" -}}
{{ .Release.Name }}-control-plane
{{- end -}}

{{- define "shellforge.web.fullname" -}}
{{ .Release.Name }}-web
{{- end -}}

{{- define "shellforge.commonEnv" -}}
- name: ENV
  value: {{ .Values.global.env | quote }}
- name: LOG_LEVEL
  value: {{ .Values.global.logLevel | quote }}
- name: DATABASE_URL
  valueFrom:
    secretKeyRef:
      name: {{ .Release.Name }}-database
      key: url
- name: OIDC_ISSUER
  value: {{ .Values.oidc.issuer | quote }}
- name: OIDC_CLIENT_ID
  value: {{ .Values.oidc.clientId | quote }}
- name: OIDC_CLIENT_SECRET
  valueFrom:
    secretKeyRef:
      name: {{ .Release.Name }}-oidc
      key: clientSecret
- name: OIDC_REDIRECT_URI
  value: {{ .Values.oidc.redirectUri | quote }}
- name: SECRET_BACKEND
  value: {{ .Values.secrets.backend | quote }}
- name: SECRET_PATH_PREFIX
  value: {{ .Values.secrets.pathPrefix | quote }}
- name: AUDIT_BACKEND
  value: {{ .Values.audit.backend | quote }}
- name: OTEL_EXPORTER_OTLP_ENDPOINT
  value: {{ .Values.audit.otelEndpoint | quote }}
- name: OTEL_EXPORTER_OTLP_PROTOCOL
  value: {{ .Values.audit.otelProtocol | quote }}
- name: COMPUTE_BACKEND
  value: {{ .Values.compute.backend | quote }}
{{- if eq .Values.compute.backend "openshell" }}
- name: OPENSHELL_GATEWAY_ENDPOINT
  value: {{ .Values.compute.openshell.endpoint | quote }}
- name: OPENSHELL_AUTH_MODE
  value: {{ .Values.compute.openshell.authMode | quote }}
- name: OPENSHELL_DEFAULT_COMPUTE_DRIVER
  value: {{ .Values.compute.openshell.defaultComputeDriver | quote }}
{{- end }}
- name: PDF_BACKEND
  value: {{ .Values.pdf.backend | quote }}
{{- end -}}
