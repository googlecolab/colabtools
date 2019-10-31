declare namespace google.colab.kernel {
  /**
   * Request that a registered method be invoked on the kernel.
   * The method must have been registered via Python using
   * `google.colab.output.register_callback`.
   *
   * @param functionName The name of the function registered on the kernel.
   * @param args Array of args passed as the Python *args argument.
   * @param kwargs Object of args passed as the Python **kwargs argument.
   */
  export function invokeFunction(
      // tslint:disable-next-line:no-any intentionally allow any params.
      functionName: string, args?: any[],
      // tslint:disable-next-line:no-any intentionally allow any params.
      kwargs?: {[key: string]: any}): Promise<unknown>;

  /**
   * Requests that the client start proxying content from the kernel's port
   * `port` to be available from the user's browser. This returns a URL which
   * can be used to access data on that port.
   *
   * @param port The TCP port number to be made available to the notebook
   *     viewer. Must be accessible as http://localhost:{port}.
   * @param cache True if the contents of HTTP GET requests should be cached in
   *     the notebook for offline viewing.
   * @return A promise resolved with a URL which can be used by the current
   *     viewer of the notebook to access the port. This URL is only valid for
   *     the current viewer while this notebook is open.
   */
  export function proxyPort(
      port: number, {cache}?: {cache?: boolean}): Promise<string>;

  /**
   * True if this is a trusted output and can communicate with the kernel.
   * Trusted outputs are outputs which were generated in the current browser
   * session.
   */
  export const accessAllowed: boolean;
}

declare namespace google.colab.output {
  /**
   * Returns the current element which outputs go to for this outputframe.
   * Unlike @getDefaultOutputArea when outputs are redirected to another element
   * then this will return that redirected element.
   */
  export function getActiveOutputArea(): Element;

  /**
   * Returns the default element which outputs go to for this outputframe.
   */
  export function getDefaultOutputArea(): Element;

  /**
   * Pause processing of additional outputs until the provided promise has been
   * resolved. This is used when asynchronous initialization must be performed.
   *
   * When outputs are initially being rendered then automatic resizing of the
   * outputframe will be paused until this promise is resolved. This can be used
   * to reduce layout jank while rendering complex outputs.
   */
  export function pauseOutputUntil(promise: Promise<void>): void;

  interface ResizeOptions {
    /** The maximum height that the outputframe is allowed to have. */
    maxHeight?: number;

    interactive?: boolean;
  }

  /**
   * Request that the outputframe get resized to the specified height.
   * @param height The height in pixels that the iframe height should be set to.
   * @param autoResize False if automatic resizing should be disabled.
   */
  export function setIframeHeight(
      height: number, autoResize?: boolean, options?: ResizeOptions): void;

  /**
   * Request that the outputframe get resized to the content height.
   * Outputs should now be using the browser's ResizeObserver so this should
   * now happen automatically.
   */
  export function resizeIframeToContent(): void;
}
