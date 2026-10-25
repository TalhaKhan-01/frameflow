import "./style.css";
import { ink } from "./ink";

ink(document.getElementById("ink") as HTMLCanvasElement, matchMedia("(prefers-reduced-motion: reduce)").matches);
