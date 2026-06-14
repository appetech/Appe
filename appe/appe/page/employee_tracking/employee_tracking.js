// frappe.pages['employee-tracking'].on_page_load = function(wrapper) {

//     let page = frappe.ui.make_app_page({
//         parent: wrapper,
//         title: 'Employee Tracking',
//         single_column: true
//     });

//     $(frappe.render_template(
//         "employee_tracking",
//         {}
//     )).appendTo(page.body);

//     load_leaflet();

//     loadEmployees();

//     $("#load_tracking").click(() => {
//         loadTracking();
//     });
// };

frappe.pages['employee-tracking'].on_page_load = function(wrapper) {

    let page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Employee Tracking',
        single_column: true
    });

    $(`
        <div class="employee-tracking-page">

            <div class="tracking-filters">
                <select id="employee"></select>

                <input
                    type="date"
                    id="tracking_date"
                    class="form-control"
                >

                <button
                    id="load_tracking"
                    class="btn btn-primary"
                >
                    Load
                </button>
            </div>

            <div class="tracking-summary">

                <div class="tracking-card">
                    <div>Distance</div>
                    <h3 id="distance">0 KM</h3>
                </div>

                <div class="tracking-card">
                    <div>Activities</div>
                    <h3 id="activities">0</h3>
                </div>

                <div class="tracking-card">
                    <div>GPS Points</div>
                    <h3 id="points">0</h3>
                </div>

                <div class="tracking-card">
                    <div>Working Hours</div>
                    <h3 id="working_hours">0</h3>
                </div>

            </div>

            <div style="display:flex;gap:15px">

                <div
                    id="tracking_map"
                    style="
                        width:70%;
                        height:700px;
                    "
                ></div>

                <div
                    id="timeline"
                    style="
                        width:30%;
                        height:700px;
                        overflow:auto;
                        background:#fff;
                        padding:15px;
                    "
                ></div>

            </div>

        </div>
    `).appendTo(page.body);

    initMap();
};

let map;
let routeLayer;
let markers=[];

function load_leaflet(){

    if(window.L){

        initMap();
        return;
    }

    $('head').append(`
        <link
         rel="stylesheet"
         href="https://unpkg.com/leaflet/dist/leaflet.css"
        />
    `);

    $.getScript(
        "https://unpkg.com/leaflet/dist/leaflet.js",
        function(){
            initMap();
        }
    );
}

function initMap(){

    map = L.map('tracking_map').setView(
        [21.2514,81.6296],
        11
    );

    L.tileLayer(
        'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
        {
            maxZoom:19
        }
    ).addTo(map);
}

async function loadTracking(){

    let employee=$("#employee").val();
    let date=$("#tracking_date").val();

    let r = await frappe.call({
        method:
        "appe.api.tracking.get_employee_tracking",
        args:{
            employee,
            date
        }
    });

    let data = r.message;

    $("#distance").text(
        data.distance + " KM"
    );

    $("#activities").text(
        data.activities
    );

    $("#points").text(
        data.points
    );

    renderRoute(data);
    renderTimeline(data);
}

function renderRoute(data){

    markers.forEach(m=>{
        map.removeLayer(m);
    });

    markers=[];

    if(routeLayer){
        map.removeLayer(routeLayer);
    }

    let geojson =
        JSON.parse(data.route_geojson);

    routeLayer = L.geoJSON(
        geojson,
        {
            style:{
                color:"#111",
                weight:5
            }
        }
    ).addTo(map);

    map.fitBounds(
        routeLayer.getBounds()
    );

    let timeline =
        JSON.parse(data.timeline_json);

    timeline.forEach(item=>{

        if(
            !item.lat ||
            !item.lng
        ) return;

        let marker = L.marker([
            item.lat,
            item.lng
        ])
        .addTo(map)
        .bindPopup(`
            <b>${item.title}</b><br>
            ${item.time}
        `);

        markers.push(marker);

    });
}

function renderTimeline(data){

    let timeline =
        JSON.parse(data.timeline_json);

    let html='';

    timeline.forEach(row=>{

        html += `
        <div class="timeline-item">

            <div class="timeline-time">
                ${row.time}
            </div>

            <div class="timeline-title">
                ${row.title}
            </div>

            <div>
                ${row.doctype || ''}
            </div>

        </div>
        `;
    });

    $("#timeline").html(html);
}

async function loadEmployees(){

    let r = await frappe.call({
        method:"frappe.client.get_list",
        args:{
            doctype:"Employee",
            fields:["name","employee_name"],
            limit_page_length:500
        }
    });

    let html='';

    r.message.forEach(emp=>{

        html += `
        <option value="${emp.name}">
            ${emp.employee_name}
        </option>
        `;
    });

    $("#employee").html(html);
}