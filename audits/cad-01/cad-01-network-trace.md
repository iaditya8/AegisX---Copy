# AegisX CAD-01 Network Request Audit Trace

This report outlines all client-side network fetch activities, API responses, latencies, and transaction results captured during the live customer onboarding walkthrough.

## Network Transaction Log

| Method | Endpoint | Status Code | Duration | Request Payload | Response Payload | Observed Impact |
| :--- | :--- | :---: | :---: | :--- | :--- | :--- |
| GET | http://localhost:3000/login | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/media/83afe278b6a6bb3c-s.p.2bn3s6zvc0dyp.woff2 | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Broot-of-the-server%5D__1_cxnk7._.css | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1xx01vv._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_next-devtools_index_090k2jm.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_react-dom_096_9a-._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_react-server-dom-turbopack_164kp-6._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_1amofcm._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_client_0r5nbpw._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_1ybzpk2._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_%40swc_helpers_cjs_1r9vbqw._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/_1anvha4._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/turbopack-_01_ro95._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_1dl7mpl._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_providers_tsx_195mga_._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_layout_tsx_007e4b2._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_19i47_j._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_0xopzvx._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_login_page_tsx_1yys4c2._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_client_components_builtin_global-error_1yys4c2.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1mojsay._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1xch-cm._.js | 200 | N/A | None | N/A | Successful API transaction. |
| POST | http://localhost:8000/api/v1/auth/token | 401 | N/A | {"username":"admin_user","password":"wrong_password"} | N/A | API request failed or returned error structure. |
| GET | http://localhost:3000/login | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/media/83afe278b6a6bb3c-s.p.2bn3s6zvc0dyp.woff2 | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Broot-of-the-server%5D__1_cxnk7._.css | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1xx01vv._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_next-devtools_index_090k2jm.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_react-dom_096_9a-._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_react-server-dom-turbopack_164kp-6._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_1amofcm._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_client_0r5nbpw._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_1ybzpk2._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_%40swc_helpers_cjs_1r9vbqw._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/_1anvha4._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/turbopack-_01_ro95._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_1dl7mpl._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_providers_tsx_195mga_._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_layout_tsx_007e4b2._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_19i47_j._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_0xopzvx._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_login_page_tsx_1yys4c2._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_client_components_builtin_global-error_1yys4c2.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1mojsay._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1xch-cm._.js | 304 | N/A | None | N/A | Successful API transaction. |
| POST | http://localhost:8000/api/v1/auth/token | 200 | N/A | {"username":"admin_user","password":"admin_password"} | {"success":true,"data":{"access_token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZjA1N2Y2MC0xYTBmLTQ5OWUtOTJhMy1 | Successful API transaction. |
| GET | http://localhost:8000/api/v1/users/me | 200 | N/A | None | {"success":true,"data":{"id":"df057f60-1a0f-499e-92a3-a7cd32b8c2a4","username":"admin_user","display_name":"Admin_user", | Successful API transaction. |
| GET | http://localhost:3000/?_rsc=yJVSf2-mUsVl2a-v | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_0k3y7_l._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_1ip7zzf._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_page_tsx_1yys4c2._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_0k3y7_l._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_1ip7zzf._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_page_tsx_1yys4c2._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:8000/api/v1/copilot/history | 200 | N/A | None | [{"id":"audit-123","user_id":"user-admin","scope_id":"scope-123","prompt":"Show posture issues","response_text":"Verify  | Successful API transaction. |
| GET | http://localhost:8000/api/v1/scopes | 200 | N/A | None | {"success":true,"data":[],"meta":{"total":0,"page":1,"page_size":50},"trace_id":null} | Successful API transaction. |
| GET | http://localhost:8000/api/v1/security-intelligence-graph/topology | 200 | N/A | None | {"nodes":[],"edges":[]} | Successful API transaction. |
| GET | http://localhost:8000/api/v1/findings | 200 | N/A | None | {"success":true,"data":[],"meta":{"total":0,"page":1,"page_size":50},"trace_id":null} | Successful API transaction. |
| GET | http://localhost:8000/api/v1/cyber-risk-quantification | 200 | N/A | None | {"success":true,"data":[],"meta":{},"trace_id":null} | Successful API transaction. |
| GET | http://localhost:8000/api/v1/security-decision | 307 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:8000/api/v1/security-decision/ | 200 | N/A | None | [] | Successful API transaction. |
| GET | http://localhost:3000/scopes | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/media/83afe278b6a6bb3c-s.p.2bn3s6zvc0dyp.woff2 | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Broot-of-the-server%5D__1_cxnk7._.css | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1xx01vv._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_next-devtools_index_090k2jm.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_react-dom_096_9a-._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_react-server-dom-turbopack_164kp-6._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_1amofcm._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_client_0r5nbpw._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_1ybzpk2._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_%40swc_helpers_cjs_1r9vbqw._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/_1anvha4._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/turbopack-_01_ro95._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_1dl7mpl._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_providers_tsx_195mga_._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_layout_tsx_007e4b2._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_0ucuin1._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_0_cchls._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_scopes_page_tsx_1yys4c2._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_client_components_builtin_global-error_1yys4c2.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1mojsay._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1xch-cm._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:8000/api/v1/copilot/history | 200 | N/A | None | [{"id":"audit-123","user_id":"user-admin","scope_id":"scope-123","prompt":"Show posture issues","response_text":"Verify  | Successful API transaction. |
| GET | http://localhost:8000/api/v1/scopes | 200 | N/A | None | {"success":true,"data":[],"meta":{"total":0,"page":1,"page_size":50},"trace_id":null} | Successful API transaction. |
| GET | http://localhost:8000/api/v1/scopes | 200 | N/A | None | {"success":true,"data":[],"meta":{"total":0,"page":1,"page_size":50},"trace_id":null} | Successful API transaction. |
| POST | http://localhost:8000/api/v1/scopes | 201 | N/A | {"name":"CIDR External Audit","type":"cidr","definition":{"targets":["192.168.0.0/24"]}} | {"success":true,"data":{"name":"CIDR External Audit","type":"cidr","definition":{"targets":["192.168.0.0/24"]},"id":"d62 | Successful API transaction. |
| GET | http://localhost:8000/api/v1/scopes | 200 | N/A | None | {"success":true,"data":[{"name":"CIDR External Audit","type":"cidr","definition":{"targets":["192.168.0.0/24"]},"id":"d6 | Successful API transaction. |
| GET | http://localhost:8000/api/v1/scopes | 200 | N/A | None | {"success":true,"data":[{"name":"CIDR External Audit","type":"cidr","definition":{"targets":["192.168.0.0/24"]},"id":"d6 | Successful API transaction. |
| POST | http://localhost:8000/api/v1/scopes | 201 | N/A | {"name":"CIDR External Audit","type":"domain","definition":{"targets":["192.168.0.0/24"]}} | {"success":true,"data":{"name":"CIDR External Audit","type":"domain","definition":{"targets":["192.168.0.0/24"]},"id":"5 | Successful API transaction. |
| GET | http://localhost:8000/api/v1/scopes | 200 | N/A | None | {"success":true,"data":[{"name":"CIDR External Audit","type":"domain","definition":{"targets":["192.168.0.0/24"]},"id":" | Successful API transaction. |
| GET | http://localhost:8000/api/v1/scopes | 200 | N/A | None | {"success":true,"data":[{"name":"CIDR External Audit","type":"domain","definition":{"targets":["192.168.0.0/24"]},"id":" | Successful API transaction. |
| GET | http://localhost:3000/workflows | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/media/83afe278b6a6bb3c-s.p.2bn3s6zvc0dyp.woff2 | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Broot-of-the-server%5D__1_cxnk7._.css | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1xx01vv._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_next-devtools_index_090k2jm.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_react-dom_096_9a-._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_react-server-dom-turbopack_164kp-6._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_1amofcm._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_client_0r5nbpw._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_1ybzpk2._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_%40swc_helpers_cjs_1r9vbqw._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/_1anvha4._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/turbopack-_01_ro95._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_1dl7mpl._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_providers_tsx_195mga_._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_layout_tsx_007e4b2._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_0fm7262._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_1-u78cm._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_workflows_page_tsx_1yys4c2._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_client_components_builtin_global-error_1yys4c2.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1mojsay._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1xch-cm._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:8000/api/v1/copilot/history | 200 | N/A | None | [{"id":"audit-123","user_id":"user-admin","scope_id":"scope-123","prompt":"Show posture issues","response_text":"Verify  | Successful API transaction. |
| GET | http://localhost:8000/api/v1/scopes | 200 | N/A | None | {"success":true,"data":[{"name":"CIDR External Audit","type":"domain","definition":{"targets":["192.168.0.0/24"]},"id":" | Successful API transaction. |
| GET | http://localhost:8000/api/v1/workflows | 200 | N/A | None | {"success":true,"data":[],"meta":{"total":0,"page":1,"page_size":50},"trace_id":null} | Successful API transaction. |
| GET | http://localhost:3000/assets | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/media/83afe278b6a6bb3c-s.p.2bn3s6zvc0dyp.woff2 | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Broot-of-the-server%5D__1_cxnk7._.css | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1xx01vv._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_next-devtools_index_090k2jm.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_react-dom_096_9a-._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_react-server-dom-turbopack_164kp-6._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_1amofcm._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_client_0r5nbpw._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_1ybzpk2._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_%40swc_helpers_cjs_1r9vbqw._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/_1anvha4._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/turbopack-_01_ro95._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_1dl7mpl._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_providers_tsx_195mga_._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_layout_tsx_007e4b2._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_0iwbwjl._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_1l1xs0h._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_assets_page_tsx_1yys4c2._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_client_components_builtin_global-error_1yys4c2.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1mojsay._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1xch-cm._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:8000/api/v1/copilot/history | 200 | N/A | None | [{"id":"audit-123","user_id":"user-admin","scope_id":"scope-123","prompt":"Show posture issues","response_text":"Verify  | Successful API transaction. |
| GET | http://localhost:8000/api/v1/scopes | 200 | N/A | None | {"success":true,"data":[{"name":"CIDR External Audit","type":"domain","definition":{"targets":["192.168.0.0/24"]},"id":" | Successful API transaction. |
| GET | http://localhost:8000/api/v1/scopes/d624946d-dfa4-44f5-9ee7-740e50c8f38e/assets | 200 | N/A | None | {"success":true,"data":[],"meta":{"total":0,"page":1,"page_size":50},"trace_id":null} | Successful API transaction. |
| GET | http://localhost:3000/findings | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/media/83afe278b6a6bb3c-s.p.2bn3s6zvc0dyp.woff2 | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Broot-of-the-server%5D__1_cxnk7._.css | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1xx01vv._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_next-devtools_index_090k2jm.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_react-dom_096_9a-._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_react-server-dom-turbopack_164kp-6._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_1amofcm._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_client_0r5nbpw._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_1ybzpk2._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_%40swc_helpers_cjs_1r9vbqw._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/_1anvha4._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/turbopack-_01_ro95._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_1dl7mpl._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_providers_tsx_195mga_._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_layout_tsx_007e4b2._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_1lmcotp._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_0gmwoec._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_findings_page_tsx_1yys4c2._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_client_components_builtin_global-error_1yys4c2.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1mojsay._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1xch-cm._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:8000/api/v1/copilot/history | 200 | N/A | None | [{"id":"audit-123","user_id":"user-admin","scope_id":"scope-123","prompt":"Show posture issues","response_text":"Verify  | Successful API transaction. |
| GET | http://localhost:8000/api/v1/scopes | 200 | N/A | None | {"success":true,"data":[{"name":"CIDR External Audit","type":"domain","definition":{"targets":["192.168.0.0/24"]},"id":" | Successful API transaction. |
| GET | http://localhost:8000/api/v1/findings?scope_id=d624946d-dfa4-44f5-9ee7-740e50c8f38e | 200 | N/A | None | {"success":true,"data":[],"meta":{"total":0,"page":1,"page_size":50},"trace_id":null} | Successful API transaction. |
| GET | http://localhost:3000/soc | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/media/83afe278b6a6bb3c-s.p.2bn3s6zvc0dyp.woff2 | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Broot-of-the-server%5D__1_cxnk7._.css | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1xx01vv._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_next-devtools_index_090k2jm.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_react-dom_096_9a-._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_react-server-dom-turbopack_164kp-6._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_1amofcm._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_client_0r5nbpw._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_1ybzpk2._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_%40swc_helpers_cjs_1r9vbqw._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/_1anvha4._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/turbopack-_01_ro95._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_1dl7mpl._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_providers_tsx_195mga_._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_layout_tsx_007e4b2._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_0lnfq2r._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_1ac6rva._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_soc_page_tsx_1yys4c2._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_client_components_builtin_global-error_1yys4c2.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1mojsay._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1xch-cm._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:8000/api/v1/copilot/history | 200 | N/A | None | [{"id":"audit-123","user_id":"user-admin","scope_id":"scope-123","prompt":"Show posture issues","response_text":"Verify  | Successful API transaction. |
| GET | http://localhost:8000/api/v1/scopes | 200 | N/A | None | {"success":true,"data":[{"name":"CIDR External Audit","type":"domain","definition":{"targets":["192.168.0.0/24"]},"id":" | Successful API transaction. |
| GET | http://localhost:8000/api/v1/security-operations-analytics/queues | 200 | N/A | None | {"success":true,"data":{"queue_size":24,"processing_efficiency":94.5,"backlog_metrics":{"alert_backlog":12,"incident_bac | Successful API transaction. |
| GET | http://localhost:8000/api/v1/security-operations-analytics/kpis | 200 | N/A | None | {"success":true,"data":[{"kpi_id":"b5c7894e-8686-4d87-b73f-f9a1e5f1c391","kpi_name":"Queue Processing Rate","current_val | Successful API transaction. |
| GET | http://localhost:8000/api/v1/security-operations-analytics/analysts | 200 | N/A | None | {"success":true,"data":[{"analyst_id":"1a1a1a1a-1a1a-1a1a-1a1a-1a1a1a1a1a1a","analyst_name":"Alice Vance","alerts_handle | Successful API transaction. |
| GET | http://localhost:8000/api/v1/cyber-resilience | 200 | N/A | None | {"success":true,"data":[],"meta":{},"trace_id":null} | Successful API transaction. |
| GET | http://localhost:3000/graph | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/media/83afe278b6a6bb3c-s.p.2bn3s6zvc0dyp.woff2 | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Broot-of-the-server%5D__1_cxnk7._.css | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1xx01vv._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_next-devtools_index_090k2jm.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_react-dom_096_9a-._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_react-server-dom-turbopack_164kp-6._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_1amofcm._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_client_0r5nbpw._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_1ybzpk2._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_%40swc_helpers_cjs_1r9vbqw._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/_1anvha4._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/turbopack-_01_ro95._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_1dl7mpl._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_providers_tsx_195mga_._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_layout_tsx_007e4b2._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_02rpcqq._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_1fufn83._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_graph_page_tsx_1yys4c2._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_client_components_builtin_global-error_1yys4c2.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1mojsay._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1xch-cm._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:8000/api/v1/copilot/history | 200 | N/A | None | [{"id":"audit-123","user_id":"user-admin","scope_id":"scope-123","prompt":"Show posture issues","response_text":"Verify  | Successful API transaction. |
| GET | http://localhost:8000/api/v1/scopes | 200 | N/A | None | {"success":true,"data":[{"name":"CIDR External Audit","type":"domain","definition":{"targets":["192.168.0.0/24"]},"id":" | Successful API transaction. |
| GET | http://localhost:8000/api/v1/security-intelligence-graph/topology | 200 | N/A | None | {"nodes":[],"edges":[]} | Successful API transaction. |
| GET | http://localhost:8000/api/v1/scopes/d624946d-dfa4-44f5-9ee7-740e50c8f38e/assets | 200 | N/A | None | {"success":true,"data":[],"meta":{"total":0,"page":1,"page_size":50},"trace_id":null} | Successful API transaction. |
| GET | http://localhost:8000/api/v1/findings | 200 | N/A | None | {"success":true,"data":[],"meta":{"total":0,"page":1,"page_size":50},"trace_id":null} | Successful API transaction. |
| GET | http://localhost:8000/api/v1/threat-intelligence?scope_id=d624946d-dfa4-44f5-9ee7-740e50c8f38e | 307 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:8000/api/v1/threat-intelligence/?scope_id=d624946d-dfa4-44f5-9ee7-740e50c8f38e | 200 | N/A | None | [] | Successful API transaction. |
| GET | http://localhost:3000/reports | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/media/83afe278b6a6bb3c-s.p.2bn3s6zvc0dyp.woff2 | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Broot-of-the-server%5D__1_cxnk7._.css | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1xx01vv._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_next-devtools_index_090k2jm.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_react-dom_096_9a-._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_react-server-dom-turbopack_164kp-6._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_compiled_1amofcm._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_client_0r5nbpw._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_1ybzpk2._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_%40swc_helpers_cjs_1r9vbqw._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/_1anvha4._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/turbopack-_01_ro95._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_1dl7mpl._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_providers_tsx_195mga_._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_layout_tsx_007e4b2._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_0o27_c1._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_0sh57zn._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/src_app_reports_page_tsx_1yys4c2._.js | 200 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/node_modules_next_dist_client_components_builtin_global-error_1yys4c2.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1mojsay._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:3000/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client_hmr-client_ts_1xch-cm._.js | 304 | N/A | None | N/A | Successful API transaction. |
| GET | http://localhost:8000/api/v1/copilot/history | 200 | N/A | None | [{"id":"audit-123","user_id":"user-admin","scope_id":"scope-123","prompt":"Show posture issues","response_text":"Verify  | Successful API transaction. |
| GET | http://localhost:8000/api/v1/scopes | 200 | N/A | None | {"success":true,"data":[{"name":"CIDR External Audit","type":"domain","definition":{"targets":["192.168.0.0/24"]},"id":" | Successful API transaction. |
| GET | http://localhost:8000/api/v1/dashboard/summary | 200 | N/A | None | {"success":true,"data":{"asset_count":0,"internet_exposed_assets":0,"open_ports":0,"services":0,"findings":{"critical":0 | Successful API transaction. |
| GET | http://localhost:8000/api/v1/dashboard/trends?days=30 | 200 | N/A | None | {"success":true,"data":{"window_days":30,"risk_trend":[],"finding_trend":[],"critical_finding_trend":[]},"meta":{},"trac | Successful API transaction. |
| GET | http://localhost:8000/api/v1/reports/exposure | 200 | N/A | None | {"success":true,"data":{"external_assets":[],"internal_assets":[],"unknown_assets":[],"internet_exposed_count":0},"meta" | Successful API transaction. |
