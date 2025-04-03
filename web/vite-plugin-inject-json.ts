import { Plugin, PluginOption } from 'vite';
import { readFileSync, writeFileSync } from 'fs';
import { resolve } from 'path';

const injectedJson = {
    "app_id": "抖音",
    "app_name": "tiktok",
    "app_version": "1.0.1",
    "scene": "douyin_0010",
    "timestamp": 1622222222,
    "perfPath": [
        "/perf/summary_report.html",
        "/perf/memory_report.html",
        "/perf/cpu_report.html"
    ],
    "categories": [
        "ABC_APP",
        "ABC_SO",
        "ABC_LIB",
        "OS_Runtime",
        "SYS",
        "RN",
        "Flutter",
        "WEB"
    ],
    "steps": [
        {
            "step_name": "步骤 1",
            "step_id": 0,
            "count": 10000,
            "data": [
                {
                    "category": 0,
                    "count": 800,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 500,
                            "files": [
                                {
                                    "file": "file1.txt",
                                    "count": 200
                                },
                                {
                                    "file": "file2.txt",
                                    "count": 300
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 300,
                            "files": [
                                {
                                    "file": "file3.txt",
                                    "count": 150
                                },
                                {
                                    "file": "file4.txt",
                                    "count": 150
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 1,
                    "count": 750,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 400,
                            "files": [
                                {
                                    "file": "file5.txt",
                                    "count": 200
                                },
                                {
                                    "file": "file6.txt",
                                    "count": 200
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 350,
                            "files": [
                                {
                                    "file": "file7.txt",
                                    "count": 150
                                },
                                {
                                    "file": "file8.txt",
                                    "count": 200
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 2,
                    "count": 700,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 450,
                            "files": [
                                {
                                    "file": "file9.txt",
                                    "count": 250
                                },
                                {
                                    "file": "file10.txt",
                                    "count": 200
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 250,
                            "files": [
                                {
                                    "file": "file11.txt",
                                    "count": 100
                                },
                                {
                                    "file": "file12.txt",
                                    "count": 150
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 3,
                    "count": 650,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 350,
                            "files": [
                                {
                                    "file": "file13.txt",
                                    "count": 150
                                },
                                {
                                    "file": "file14.txt",
                                    "count": 200
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 300,
                            "files": [
                                {
                                    "file": "file15.txt",
                                    "count": 100
                                },
                                {
                                    "file": "file16.txt",
                                    "count": 200
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 4,
                    "count": 600,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 300,
                            "files": [
                                {
                                    "file": "file17.txt",
                                    "count": 100
                                },
                                {
                                    "file": "file18.txt",
                                    "count": 200
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 300,
                            "files": [
                                {
                                    "file": "file19.txt",
                                    "count": 150
                                },
                                {
                                    "file": "file20.txt",
                                    "count": 150
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 5,
                    "count": 550,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 300,
                            "files": [
                                {
                                    "file": "file21.txt",
                                    "count": 150
                                },
                                {
                                    "file": "file22.txt",
                                    "count": 150
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 250,
                            "files": [
                                {
                                    "file": "file23.txt",
                                    "count": 100
                                },
                                {
                                    "file": "file24.txt",
                                    "count": 150
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 6,
                    "count": 500,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 250,
                            "files": [
                                {
                                    "file": "file25.txt",
                                    "count": 100
                                },
                                {
                                    "file": "file26.txt",
                                    "count": 150
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 250,
                            "files": [
                                {
                                    "file": "file27.txt",
                                    "count": 120
                                },
                                {
                                    "file": "file28.txt",
                                    "count": 130
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 7,
                    "count": 450,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 200,
                            "files": [
                                {
                                    "file": "file29.txt",
                                    "count": 80
                                },
                                {
                                    "file": "file30.txt",
                                    "count": 120
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 250,
                            "files": [
                                {
                                    "file": "file31.txt",
                                    "count": 100
                                },
                                {
                                    "file": "file32.txt",
                                    "count": 150
                                }
                            ]
                        }
                    ]
                }
            ]
        },
        {
            "step_name": "步骤 2",
            "step_id": 1,
            "count": 8000,
            "data": [
                {
                    "category": 0,
                    "count": 600,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 350,
                            "files": [
                                {
                                    "file": "file33.txt",
                                    "count": 150
                                },
                                {
                                    "file": "file34.txt",
                                    "count": 200
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 250,
                            "files": [
                                {
                                    "file": "file35.txt",
                                    "count": 100
                                },
                                {
                                    "file": "file36.txt",
                                    "count": 150
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 1,
                    "count": 550,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 300,
                            "files": [
                                {
                                    "file": "file37.txt",
                                    "count": 120
                                },
                                {
                                    "file": "file38.txt",
                                    "count": 180
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 250,
                            "files": [
                                {
                                    "file": "file39.txt",
                                    "count": 100
                                },
                                {
                                    "file": "file40.txt",
                                    "count": 150
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 2,
                    "count": 500,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 250,
                            "files": [
                                {
                                    "file": "file41.txt",
                                    "count": 100
                                },
                                {
                                    "file": "file42.txt",
                                    "count": 150
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 250,
                            "files": [
                                {
                                    "file": "file43.txt",
                                    "count": 120
                                },
                                {
                                    "file": "file44.txt",
                                    "count": 130
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 3,
                    "count": 450,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 200,
                            "files": [
                                {
                                    "file": "file45.txt",
                                    "count": 80
                                },
                                {
                                    "file": "file46.txt",
                                    "count": 120
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 250,
                            "files": [
                                {
                                    "file": "file47.txt",
                                    "count": 100
                                },
                                {
                                    "file": "file48.txt",
                                    "count": 150
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 4,
                    "count": 400,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 200,
                            "files": [
                                {
                                    "file": "file49.txt",
                                    "count": 80
                                },
                                {
                                    "file": "file50.txt",
                                    "count": 120
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 200,
                            "files": [
                                {
                                    "file": "file51.txt",
                                    "count": 100
                                },
                                {
                                    "file": "file52.txt",
                                    "count": 100
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 5,
                    "count": 350,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 150,
                            "files": [
                                {
                                    "file": "file53.txt",
                                    "count": 60
                                },
                                {
                                    "file": "file54.txt",
                                    "count": 90
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 200,
                            "files": [
                                {
                                    "file": "file55.txt",
                                    "count": 80
                                },
                                {
                                    "file": "file56.txt",
                                    "count": 120
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 6,
                    "count": 300,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 150,
                            "files": [
                                {
                                    "file": "file57.txt",
                                    "count": 60
                                },
                                {
                                    "file": "file58.txt",
                                    "count": 90
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 150,
                            "files": [
                                {
                                    "file": "file59.txt",
                                    "count": 70
                                },
                                {
                                    "file": "file60.txt",
                                    "count": 80
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 7,
                    "count": 250,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 100,
                            "files": [
                                {
                                    "file": "file61.txt",
                                    "count": 40
                                },
                                {
                                    "file": "file62.txt",
                                    "count": 60
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 150,
                            "files": [
                                {
                                    "file": "file63.txt",
                                    "count": 60
                                },
                                {
                                    "file": "file64.txt",
                                    "count": 90
                                }
                            ]
                        }
                    ]
                }
            ]
        },
        {
            "step_name": "步骤 3",
            "step_id": 2,
            "count": 6000,
            "data": [
                {
                    "category": 0,
                    "count": 400,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 200,
                            "files": [
                                {
                                    "file": "file65.txt",
                                    "count": 80
                                },
                                {
                                    "file": "file66.txt",
                                    "count": 120
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 200,
                            "files": [
                                {
                                    "file": "file67.txt",
                                    "count": 100
                                },
                                {
                                    "file": "file68.txt",
                                    "count": 100
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 1,
                    "count": 350,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 150,
                            "files": [
                                {
                                    "file": "file69.txt",
                                    "count": 60
                                },
                                {
                                    "file": "file70.txt",
                                    "count": 90
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 200,
                            "files": [
                                {
                                    "file": "file71.txt",
                                    "count": 80
                                },
                                {
                                    "file": "file72.txt",
                                    "count": 120
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 2,
                    "count": 300,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 150,
                            "files": [
                                {
                                    "file": "file73.txt",
                                    "count": 60
                                },
                                {
                                    "file": "file74.txt",
                                    "count": 90
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 150,
                            "files": [
                                {
                                    "file": "file75.txt",
                                    "count": 70
                                },
                                {
                                    "file": "file76.txt",
                                    "count": 80
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 3,
                    "count": 250,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 100,
                            "files": [
                                {
                                    "file": "file77.txt",
                                    "count": 40
                                },
                                {
                                    "file": "file78.txt",
                                    "count": 60
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 150,
                            "files": [
                                {
                                    "file": "file79.txt",
                                    "count": 60
                                },
                                {
                                    "file": "file80.txt",
                                    "count": 90
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 4,
                    "count": 200,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 100,
                            "files": [
                                {
                                    "file": "file81.txt",
                                    "count": 40
                                },
                                {
                                    "file": "file82.txt",
                                    "count": 60
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 100,
                            "files": [
                                {
                                    "file": "file83.txt",
                                    "count": 50
                                },
                                {
                                    "file": "file84.txt",
                                    "count": 50
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 5,
                    "count": 150,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 70,
                            "files": [
                                {
                                    "file": "file85.txt",
                                    "count": 30
                                },
                                {
                                    "file": "file86.txt",
                                    "count": 40
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 80,
                            "files": [
                                {
                                    "file": "file87.txt",
                                    "count": 35
                                },
                                {
                                    "file": "file88.txt",
                                    "count": 45
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 6,
                    "count": 100,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 50,
                            "files": [
                                {
                                    "file": "file89.txt",
                                    "count": 20
                                },
                                {
                                    "file": "file90.txt",
                                    "count": 30
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 50,
                            "files": [
                                {
                                    "file": "file91.txt",
                                    "count": 25
                                },
                                {
                                    "file": "file92.txt",
                                    "count": 25
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 7,
                    "count": 50,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 20,
                            "files": [
                                {
                                    "file": "file93.txt",
                                    "count": 8
                                },
                                {
                                    "file": "file94.txt",
                                    "count": 12
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 30,
                            "files": [
                                {
                                    "file": "file95.txt",
                                    "count": 12
                                },
                                {
                                    "file": "file96.txt",
                                    "count": 18
                                }
                            ]
                        }
                    ]
                }
            ]
        },
        {
            "step_name": "步骤 4",
            "step_id": 3,
            "count": 4000,
            "data": [
                {
                    "category": 0,
                    "count": 200,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 100,
                            "files": [
                                {
                                    "file": "file97.txt",
                                    "count": 40
                                },
                                {
                                    "file": "file98.txt",
                                    "count": 60
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 100,
                            "files": [
                                {
                                    "file": "file99.txt",
                                    "count": 50
                                },
                                {
                                    "file": "file100.txt",
                                    "count": 50
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 1,
                    "count": 150,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 70,
                            "files": [
                                {
                                    "file": "file101.txt",
                                    "count": 30
                                },
                                {
                                    "file": "file102.txt",
                                    "count": 40
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 80,
                            "files": [
                                {
                                    "file": "file103.txt",
                                    "count": 35
                                },
                                {
                                    "file": "file104.txt",
                                    "count": 45
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 2,
                    "count": 100,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 50,
                            "files": [
                                {
                                    "file": "file105.txt",
                                    "count": 20
                                },
                                {
                                    "file": "file106.txt",
                                    "count": 30
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 50,
                            "files": [
                                {
                                    "file": "file107.txt",
                                    "count": 25
                                },
                                {
                                    "file": "file108.txt",
                                    "count": 25
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 3,
                    "count": 50,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 20,
                            "files": [
                                {
                                    "file": "file109.txt",
                                    "count": 8
                                },
                                {
                                    "file": "file110.txt",
                                    "count": 12
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 30,
                            "files": [
                                {
                                    "file": "file111.txt",
                                    "count": 12
                                },
                                {
                                    "file": "file112.txt",
                                    "count": 18
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 4,
                    "count": 20,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 10,
                            "files": [
                                {
                                    "file": "file113.txt",
                                    "count": 4
                                },
                                {
                                    "file": "file114.txt",
                                    "count": 6
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 10,
                            "files": [
                                {
                                    "file": "file115.txt",
                                    "count": 5
                                },
                                {
                                    "file": "file116.txt",
                                    "count": 5
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 5,
                    "count": 10,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 5,
                            "files": [
                                {
                                    "file": "file117.txt",
                                    "count": 2
                                },
                                {
                                    "file": "file118.txt",
                                    "count": 3
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 5,
                            "files": [
                                {
                                    "file": "file119.txt",
                                    "count": 2
                                },
                                {
                                    "file": "file120.txt",
                                    "count": 3
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 6,
                    "count": 5,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 2,
                            "files": [
                                {
                                    "file": "file121.txt",
                                    "count": 1
                                },
                                {
                                    "file": "file122.txt",
                                    "count": 1
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 3,
                            "files": [
                                {
                                    "file": "file123.txt",
                                    "count": 1
                                },
                                {
                                    "file": "file124.txt",
                                    "count": 2
                                }
                            ]
                        }
                    ]
                },
                {
                    "category": 7,
                    "count": 2,
                    "subData": [
                        {
                            "name": "子项 1",
                            "count": 1,
                            "files": [
                                {
                                    "file": "file125.txt",
                                    "count": 0
                                },
                                {
                                    "file": "file126.txt",
                                    "count": 1
                                }
                            ]
                        },
                        {
                            "name": "子项 2",
                            "count": 1,
                            "files": [
                                {
                                    "file": "file127.txt",
                                    "count": 0
                                },
                                {
                                    "file": "file128.txt",
                                    "count": 1
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ]
};


const injectJson: Plugin = {
    name: 'inject-json',
    transformIndexHtml(html) {
        const jsonScript = `<script>window.jsonData = ${JSON.stringify(injectedJson)};</script>`;
        html = html.replace('</body>', `${jsonScript}</body>`);
        return html;
    }
};

export default injectJson;