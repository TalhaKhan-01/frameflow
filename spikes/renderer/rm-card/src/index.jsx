import { registerRoot, Composition } from "remotion";
import { Card } from "./Card.jsx";

const Root = () => (
  <Composition id="Card" component={Card} durationInFrames={150} fps={30} width={1080} height={1920} />
);
registerRoot(Root);
