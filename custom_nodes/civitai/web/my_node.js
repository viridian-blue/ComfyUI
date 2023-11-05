import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js"

console.log("[logging]", "extension init");

function newCaroussel(...items) {
	console.log("newCaroussel", items);
	const elements = {};
	const ids = [];
	let current_index = 0;
	for (let item of items) {
		elements[item.id] = item;
		ids.push(item.id.toString());
	}
	return {
		elements,
		ids,
		current_index,		
		next() {
			this.current_index = (this.current_index + 1) % this.ids.length;
			console.log("next", this);
			return this.elements[this.ids[this.current_index]];
		},
		add(item) {
			if (this.elements[item.id] == null) {
				this.elements[item.id] = item;
				this.ids.push(item.id.toString());
			}
		},
		clear() {
			this.elements = {};
			this.ids = [];
			this.current_index = 0;
		},
		peek() {
			const index = (this.current_index + 1) % this.ids.length;
			return this.elements[this.ids[index]];
		},
		get value() {
			return this.elements[this.ids[this.current_index]];
		},
		skipTo(id) {
			const index = this.ids.indexOf(id.toString());
			if (index === -1) {
				console.error("id not found", id, this.ids);
				throw new Error("id not found");
			}
			this.current_index = index;
			return this.elements[this.ids[this.current_index]];
		},
		isEmpty() {
			return this.ids.length === 0;
		},
	};
}


async function getModels(params) {
	console.log("getModels", params);
	const queryParam = new URLSearchParams(params);
	const url = api.apiURL("/custom_nodes/civitai/api/v1/models") + "?" + queryParam.toString();
	console.log("getModels", url);
	const resp = await fetch(url)
	return await resp.json();
}

async function getModelVersion(versionId) {
	const url = api.apiURL("/custom_nodes/civitai/api/v1/model-versions/" + versionId);
	const resp = await fetch(url);
	if (resp.status !== 200) {
		throw new Error("error getting model version " + versionId);
	}
	return await resp.json();
}

async function getModel(modelId) {
	const url = api.apiURL("/custom_nodes/civitai/api/v1/models/" + modelId);
	const resp = await fetch(url);
	if (resp.status !== 200) {
		throw new Error("error getting model " + modelId);
	}
	return await resp.json();
}

async function updateModelCaroussel(caroussel, current_version_id, params) {
	const items = [];
	if (current_version_id) {
		try {
	  		const current = await getModelVersion(current_version_id);
			items.push(current);
		} catch (e) {
			console.error(e);
		}
	}
	const models = await getModels(params);
	const primaryVersions = models.items.map(m => m.modelVersions[0]);
	items.push(...primaryVersions);
	for (let item of items) {
		caroussel.add(item);
	}
}

async function ensureCarousselContains(caroussel, current_version_id, params) {
	const items = [];
	console.log("createActiveModelSingletonCaroussel", current_version_id);
	if (current_version_id) {
		try {
			const current = await getModelVersion(current_version_id);
			items.push(current);
		} catch (e) {
			console.error("error getting current version", e);
		}
	}
	if (items.length === 0) {
		return null;
	}
	for (let item of items) {
		caroussel.add(item);
	}
	return caroussel;
}

function createCarousselElement(caroussel) {
	const elem = document.createElement("div");
	elem.style.width = "100%";
	elem.style.height = "100%";
	elem.style.overflow = "hidden";

	const title = document.createElement("h2");
	title.style.color = "white";
	title.style.margin = "0px";
	title.style.padding = "0px";
	elem.appendChild(title);
	
	const model = caroussel?.value?.model;
	if (model) {
		title.innerText = caroussel?.value?.model?.name;
	} else {
		const modelId = caroussel?.value?.modelId;
		if (modelId) {
			getModel(modelId).then(model => {
				title.innerText = model.name;
			}).catch(e => {
				console.error(e);
			});
		}
	}

	const subtitle = document.createElement("h3");
	subtitle.style.color = "white";
	subtitle.style.margin = "0px";
	subtitle.style.padding = "0px";
	subtitle.innerText = caroussel?.value?.name;
	elem.appendChild(subtitle);

	const description = document.createElement("div");
	description.style.color = "white";
	description.style.margin = "0px";
	description.style.padding = "15px 0px";
	description.style.textAlign = "left";
	description.style.maxWidth = "100%";
	description.innerHTML = caroussel?.value?.description;
	elem.appendChild(description);

	const img = document.createElement("img");
	img.style.objectFit = "contain";
	img.style.width = "100%";
	img.style.height = "100%";
	elem.appendChild(img);
	img.src = caroussel?.value?.images?.[0]?.url;

	return elem;
}

class CivitaiModelGalleryWidget {
	constructor(node, inputName, inputData, app, modelType) {
		this.node = node;
		this.inputName = inputName;
		this.inputData = inputData;
		this.app = app;
		this.modelType = modelType;
		this.root = document.createElement("div");
		this.caroussel = newCaroussel();
		this._init();
	}

	_init() {
		this.filterContainer = document.createElement("div");
		this.filterContainer.style.pointerEvents = "auto";
		this.filterContainer.style.color = "white";
		this.baseModelFilter = document.createElement("select");
		this.baseModelFilter.style.pointerEvents = "auto";
		const options = ["", "SD 1.5", "SDXL 1.0"];
		for (let option of options) {
			const opt = document.createElement("option");
			opt.value = option;
			opt.innerText = option;
			this.baseModelFilter.appendChild(opt);
		}
		const wrapper = document.createElement("p");
		wrapper.innerText = "Base Model ";
		wrapper.appendChild(this.baseModelFilter);
		this.filterContainer.appendChild(wrapper);

		this.periodFilter = document.createElement("select");
		this.periodFilter.style.pointerEvents = "auto";
		const periods = ["Month", "AllTime", "Year", "Week", "Day"];
		for (let period of periods) {
			const opt = document.createElement("option");
			opt.value = period;
			opt.innerText = period;
			this.periodFilter.appendChild(opt);
		}
		const wrapper2 = document.createElement("p");
		wrapper2.innerText = "Period ";
		wrapper2.appendChild(this.periodFilter);

		this.filterContainer.appendChild(wrapper2);
		
		this.filterContainer.onchange = () => {
			console.log("filter changed", this.baseModelFilter.value);
			this.refresh(this.value, true);
		}

		this.root.appendChild(this.filterContainer);


		this.valueContainer = document.createElement("p");
		this.valueContainer.style.pointerEvents = "auto";
		this.root.appendChild(this.valueContainer);

		this.carousselContainer = document.createElement("div");
		this.carousselContainer.style.pointerEvents = "auto";
		this.carousselContainer.style.width = "100%";
		this.carousselContainer.style.height = "100%";
		this.carousselContainer.onclick = () => {
			this.value = this.caroussel.peek()?.id || this.value;
			this.update();
		}

		this.root.appendChild(this.carousselContainer);

		this.value = this.inputData[1].default || "";

		this.refresh(this.value);
	}

	get name() {
		return this.inputName;
	}

	get type() {
		return "civitaigallery"
	}

	get value() {
		if (this.exactVersionSource && this.exactVersionSource.value) {
			console.log("exact version source", this.exactVersionSource.value);
			return this.exactVersionSource.value.toString();
		}
		return (this._value || "").toString();
	}

	set value(val) {
		console.log("set value", val);
		if (val == null) {
			throw new Error("value cannot be null");
		}
		this._value = val;
		this.update();
	}

	headerSize() {
		return 30;
	}

	imageSize(width) {
		return [width, width * 3 / 2];
	}

	computeSize(widgetWidth) {
		return [widgetWidth, this.headerSize() + this.imageSize(widgetWidth)[1]];
	}

	update() {
		this.valueContainer.innerText = this.value;
		this.carousselContainer.innerHTML = "";
		
		if (this.caroussel.isEmpty()) {
			return;
		}
	
		ensureCarousselContains(this.caroussel, this.value, {}).then(caroussel => {
			this.caroussel.skipTo(this.value);
			console.log("got caroussel", this.caroussel, this.value);
			const elem = createCarousselElement(this.caroussel);
			this.carousselContainer.appendChild(elem);
		}).catch(e => {
			console.error(e);
		});
	}

	refresh(value, force = false) {
		value = value || this.value;
		if (force) {
			this.caroussel.clear();
		}
		if (this.exactVersionSource && this.exactVersionSource.value) {
			value = this.exactVersionSource.value;
		}

		console.log("refreshing with value", value);
		const params = { "types": this.modelType };
		if (this.baseModelFilter.value) {
			params.baseModels = this.baseModelFilter.value;
		}

		if (this.periodFilter.value) {
			params.period = this.periodFilter.value;
		}
		updateModelCaroussel(this.caroussel, value, params).then(caroussel => {
			this.isRefreshing = false;
			this.update();
		}).catch(e => {
			console.error(e);
			this.isRefreshing = false;
		});
	}

	draw(ctx, node, widgetWidth, y, widgetHeight) {
		let [w, h] = this.computeSize(widgetWidth);
		if (node.size[1]) {
			h = Math.min(h, node.size[1] - y)
		}
		// let's just draw a pink rectangle for now,
		// and add a div on top of it
		
		const transform = new DOMMatrix()
				.multiplySelf(ctx.getTransform())

		// We're drawing on a canvas in a given coordinate system. To align
		// first calculate the rectangle of the canvas in the window
		// before scaling, and then apply the scale part of the transform


		this.root.style.position = "absolute";
		this.root.style.left = "0px";
		this.root.style.top = "0px";
		this.root.style.width = w + "px";
		this.root.style.height = h + "px";
		this.root.style.transformOrigin = "0 0";
		this.root.style.transform = ` ${transform.toString()} translate(0, ${y}px)`;
		this.root.style.backgroundColor = "transparent";
		this.root.style.pointerEvents = "none";
		this.root.style.overflow = "hidden";
		this.root.style.fontFamily = "Arial";
		this.root.style.fontSize = "12px";
		this.root.style.color = "black";
		this.root.style.textAlign = "center";
		
		if (this.root.parentNode == null) {
			document.body.appendChild(this.root);
		}
	}

	onRemoved() {
		console.log("onRemove");
		this.root.remove();
	}
}

const ext = {
	// Unique name for the extension
	name: "Example.LoggingExtension",
	async getCustomWidgets(app) {

		return {
			CIVITAI_CHECKPOINT(node, inputName, inputData, app) {
				let widget = new CivitaiModelGalleryWidget(node, inputName, inputData, app, "Checkpoint");
				let res = { widget: node.addCustomWidget(widget) };

				const w0 = node.widgets[0];
				if (w0.name === "exact_version_id") {
					widget.exactVersionSource = w0;
				}

				const onRemoved = node.onRemoved;
				node.onRemoved = function() {
					widget.onRemoved();
					if (onRemoved) {
						onRemoved.call(this, ...arguments);
					}
				}

				if(inputData[1].dynamicPrompts != undefined)
					res.widget.dynamicPrompts = inputData[1].dynamicPrompts;

				return res;
			},
			CIVITAI_LORA(node, inputName, inputData, app) {
				let widget = new CivitaiModelGalleryWidget(node, inputName, inputData, app, "LORA");
				let res = { widget: node.addCustomWidget(widget) };

				const w0 = node.widgets[0];
				if (w0.name === "exact_version_id") {
					widget.exactVersionSource = w0;
				}
				
				const onRemoved = node.onRemoved;
				node.onRemoved = function() {
					widget.onRemoved();
					if (onRemoved) {
						onRemoved.call(this, ...arguments);
					}
				}

				if(inputData[1].dynamicPrompts != undefined)
					res.widget.dynamicPrompts = inputData[1].dynamicPrompts;

				return res;
			},
		}
	},
};

app.registerExtension(ext);

async function hello() {
	const url = api.apiURL("/custom_nodes/civitai/hello");
	const resp = await fetch(url);
	console.log(await resp.text());
}

hello();